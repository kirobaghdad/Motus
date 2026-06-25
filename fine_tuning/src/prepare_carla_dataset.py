from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from common import COCO80_NAMES, load_yaml, project_root, resolve_path, write_json, write_yaml


SPLIT_FILES = {
    "train": "train_yolo.txt",
    "val": "val_yolo.txt",
    "test": "test_yolo.txt",
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# roboflow writes "valid"; ultralytics expects "val".
ROBOFLOW_SPLIT_MAP = {
    "train": "train",
    "valid": "val",
    "val": "val",
    "test": "test",
}


def normalize_name(name: str) -> str:
    """normalize class names before comparing mappings."""
    # source names mostly differ by spaces and dashes.
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def names_from_id_mapping(raw: dict | list) -> list[str]:
    """return class names ordered by class id."""
    # yaml may store names as a list or id:name mapping.
    if isinstance(raw, list):
        return [str(name) for name in raw]

    keyed = {int(class_id): str(name) for class_id, name in raw.items()}
    return [keyed[class_id] for class_id in sorted(keyed)]


def clone_dataset(repo_url: str, branch: str, raw_dir: Path) -> None:
    """clone the older github dataset if it is not already present."""
    raw_dir.parent.mkdir(parents=True, exist_ok=True)
    if raw_dir.exists():
        print(f"dataset exists: {raw_dir}")
        return

    print(f"cloning dataset: {raw_dir}")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(raw_dir)],
        check=True,
    )


def read_expected_names(config: dict) -> list[str]:
    """read the configured final class order."""
    raw = config["dataset"]["custom_names"]
    return names_from_id_mapping(raw)


def validate_dataset_names(raw_dir: Path, expected_names: list[str]) -> None:
    """stop early if dataset labels do not match the config order."""
    labels_txt = raw_dir / "labels.txt"
    if not labels_txt.exists():
        raise FileNotFoundError(f"Missing dataset class list: {labels_txt}")

    actual = [line.strip() for line in labels_txt.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [normalize_name(x) for x in actual] != [normalize_name(x) for x in expected_names]:
        raise ValueError(
            "Dataset class names do not match the configured class order.\n"
            f"Expected: {expected_names}\n"
            f"Actual:   {actual}\n"
            "metrics can be mapped incorrectly if not fixed."
        )

    print("class order ok")
    for idx, name in enumerate(expected_names):
        print(f"  {idx}: {name}")


def find_label_root(raw_dir: Path) -> Path:
    """find the label folder used by the older dataset layout."""
    candidates = [raw_dir / "labels_yolo_format", raw_dir / "yolo_labels"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find YOLO labels folder: labels_yolo_format/ or yolo_labels/")


def locate_image(raw_dir: Path, rel_path_text: str, target_split: str) -> Path:
    """resolve an image path listed in an older split file."""
    rel = Path(rel_path_text.strip().replace("\\", "/").lstrip("./"))
    direct = raw_dir / rel
    if direct.exists():
        return direct

    filename = rel.name
    preferred = raw_dir / "images" / target_split / filename
    if preferred.exists():
        return preferred

    matches = sorted((raw_dir / "images").glob(f"*/{filename}"))
    if len(matches) == 1:
        return matches[0]
    if matches:
        # some split files point to old folders.
        preferred_parent = "test" if target_split == "test" else "train"
        for match in matches:
            if match.parent.name == preferred_parent:
                return match
        return matches[0]

    raise FileNotFoundError(f"Could not locate image listed in split file: {rel_path_text}")


def locate_label(label_root: Path, source_image: Path) -> Path:
    """find the yolo label file for one source image."""
    label_name = source_image.with_suffix(".txt").name
    source_split = source_image.parent.name
    direct = label_root / source_split / label_name
    if direct.exists():
        return direct

    matches = sorted(label_root.glob(f"*/{label_name}"))
    if len(matches) == 1:
        return matches[0]
    if matches:
        for match in matches:
            if match.parent.name == source_split:
                return match
        return matches[0]

    raise FileNotFoundError(f"Could not locate YOLO label for image: {source_image}")


def clean_dataset_dirs(custom_dir: Path, baseline_dir: Path, force: bool) -> None:
    """prepare empty folders for custom and baseline dataset views."""
    # both views share images but use different class ids.
    for dataset_dir in [custom_dir, baseline_dir]:
        if dataset_dir.exists() and force:
            shutil.rmtree(dataset_dir)
        for sub in ["images/train", "images/val", "images/test", "labels/train", "labels/val", "labels/test"]:
            (dataset_dir / sub).mkdir(parents=True, exist_ok=True)


def format_coord(value: float) -> str:
    """format yolo coordinates without noisy trailing zeros."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def parse_yolo_label(line: str, max_custom_id: int) -> tuple[int, list[str]]:
    """parse a yolo box or polygon label line."""
    parts = line.strip().split()
    if not parts:
        raise ValueError("Empty label line")
    class_id = int(float(parts[0]))
    if class_id < 0 or class_id > max_custom_id:
        raise ValueError(f"Unexpected custom class id {class_id}; expected 0..{max_custom_id}")

    if len(parts) == 5:
        return class_id, parts[1:]

    if len(parts) > 5 and (len(parts) - 1) % 2 == 0:
        # roboflow polygons are reduced to the outer box.
        values = [float(value) for value in parts[1:]]
        xs = values[0::2]
        ys = values[1::2]
        x_min = max(0.0, min(xs))
        x_max = min(1.0, max(xs))
        y_min = max(0.0, min(ys))
        y_max = min(1.0, max(ys))

        width = x_max - x_min
        height = y_max - y_min
        if width <= 0 or height <= 0:
            raise ValueError(f"YOLO polygon converted to an empty box: {line!r}")

        x_center = x_min + width / 2
        y_center = y_min + height / 2
        return class_id, [format_coord(value) for value in [x_center, y_center, width, height]]

    raise ValueError(
        "YOLO label must be a 5-column box or a polygon with x/y pairs, "
        f"got {len(parts)} columns: {line!r}"
    )


def copy_split(
    raw_dir: Path,
    label_root: Path,
    custom_dir: Path,
    baseline_dir: Path,
    split: str,
    split_file: Path,
    expected_names: list[str],
    coco_mapping: dict[int, dict],
) -> dict:
    """copy one older-format split into custom and baseline views."""
    # path for the older github dataset format.
    image_lines = [line.strip() for line in split_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    class_counts = Counter()
    empty_labels = 0
    copied = 0

    for rel_image in image_lines:
        source_image = locate_image(raw_dir, rel_image, split)
        source_label = locate_label(label_root, source_image)

        dest_image_custom = custom_dir / "images" / split / source_image.name
        dest_image_baseline = baseline_dir / "images" / split / source_image.name
        shutil.copy2(source_image, dest_image_custom)
        shutil.copy2(source_image, dest_image_baseline)

        custom_label_lines: list[str] = []
        baseline_label_lines: list[str] = []

        raw_label_text = source_label.read_text(encoding="utf-8").splitlines()
        for raw_line in raw_label_text:
            if not raw_line.strip():
                continue
            custom_id, coords = parse_yolo_label(raw_line, len(expected_names) - 1)
            class_counts[custom_id] += 1
            custom_label_lines.append(" ".join([str(custom_id), *coords]))

            coco_id = int(coco_mapping[custom_id]["coco_id"])
            baseline_label_lines.append(" ".join([str(coco_id), *coords]))

        if not custom_label_lines:
            empty_labels += 1

        (custom_dir / "labels" / split / source_image.with_suffix(".txt").name).write_text(
            "\n".join(custom_label_lines) + ("\n" if custom_label_lines else ""),
            encoding="utf-8",
        )
        (baseline_dir / "labels" / split / source_image.with_suffix(".txt").name).write_text(
            "\n".join(baseline_label_lines) + ("\n" if baseline_label_lines else ""),
            encoding="utf-8",
        )
        copied += 1

    return {
        "images": copied,
        "empty_label_files": empty_labels,
        "objects_by_class_id": {str(k): v for k, v in sorted(class_counts.items())},
        "objects_by_class_name": {expected_names[k]: v for k, v in sorted(class_counts.items())},
    }


def write_data_yamls(custom_dir: Path, baseline_dir: Path, expected_names: list[str]) -> tuple[Path, Path]:
    """write ultralytics data.yaml files for both dataset views."""
    custom_yaml = custom_dir / "data.yaml"
    baseline_yaml = baseline_dir / "data.yaml"

    # custom labels train the fine-tuned model.
    write_yaml(
        custom_yaml,
        {
            "path": str(custom_dir.resolve()),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(expected_names),
            "names": {idx: name for idx, name in enumerate(expected_names)},
        },
    )
    # coco labels keep the pretrained baseline fair.
    write_yaml(
        baseline_yaml,
        {
            "path": str(baseline_dir.resolve()),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(COCO80_NAMES),
            "names": {idx: name for idx, name in enumerate(COCO80_NAMES)},
        },
    )
    return custom_yaml, baseline_yaml


def require_roboflow_api_key() -> str:
    """read the roboflow api key from the environment."""
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ROBOFLOW_API_KEY is not set."
        )
    return api_key


def download_roboflow_source(source_cfg: dict, raw_root: Path, model_format: str) -> Path:
    """download one roboflow source dataset if needed."""
    source_name = source_cfg["name"]
    source_dir = raw_root / source_cfg.get("raw_subdir", source_name)
    data_yaml = source_dir / "data.yaml"
    if data_yaml.exists():
        print(f"roboflow dataset exists: {source_dir}")
        return source_dir

    if source_dir.exists() and any(source_dir.iterdir()):
        raise FileNotFoundError(
            f"Roboflow download folder exists but is missing data.yaml: {source_dir}"
        )

    print(f"downloading roboflow dataset: {source_name}")
    api_key = require_roboflow_api_key()

    from roboflow import Roboflow

    rf = Roboflow(api_key=api_key)
    project = rf.workspace(source_cfg["workspace"]).project(source_cfg["project"])
    dataset = project.version(int(source_cfg["version"])).download(
        model_format,
        location=str(source_dir),
        overwrite=False,
    )

    downloaded_dir = Path(getattr(dataset, "location", source_dir))
    if (downloaded_dir / "data.yaml").exists():
        return downloaded_dir
    if data_yaml.exists():
        return source_dir

    raise FileNotFoundError(f"Roboflow download finished, but data.yaml was not found in {source_dir}")


def read_yolo_data_names(data_yaml: Path) -> list[str]:
    """read class names from a roboflow data.yaml."""
    data = load_yaml(data_yaml)
    return names_from_id_mapping(data["names"])


def validate_source_names(source_dir: Path, source_cfg: dict) -> list[str]:
    """check one roboflow source class order against the config."""
    # source order must match the configured label ids.
    data_yaml = source_dir / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"Missing Roboflow data.yaml: {data_yaml}")

    expected = names_from_id_mapping(source_cfg["expected_names"])
    actual = read_yolo_data_names(data_yaml)
    if [normalize_name(x) for x in actual] != [normalize_name(x) for x in expected]:
        raise ValueError(
            "Roboflow source class names do not match the configured class order.\n"
            f"Source:   {source_cfg['name']}\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    print(f"class order ok: {source_cfg['name']}")
    for idx, name in enumerate(expected):
        print(f"  {idx}: {name}")
    return actual


def validate_coco_mapping(expected_names: list[str], coco_mapping: dict[int, dict]) -> None:
    """check that the coco baseline mapping follows the custom labels."""
    # baseline rows follow the custom class order.
    for class_id, custom_name in enumerate(expected_names):
        if class_id not in coco_mapping:
            raise ValueError(f"Missing baseline COCO mapping for class id {class_id}: {custom_name}")
        mapped_name = coco_mapping[class_id]["custom_name"]
        if normalize_name(mapped_name) != normalize_name(custom_name):
            raise ValueError(
                "Baseline COCO mapping does not match custom class order.\n"
                f"Class {class_id}: expected {custom_name!r}, mapping has {mapped_name!r}"
            )


def normalized_class_map(source_cfg: dict, expected_names: list[str]) -> dict[str, str]:
    """normalize source-to-target class mappings."""
    # source labels map into the final 12-class schema.
    target_names = {normalize_name(name) for name in expected_names}
    mapping = {normalize_name(source): target for source, target in source_cfg["class_map"].items()}

    for source_name, target_name in mapping.items():
        if normalize_name(target_name) not in target_names:
            raise ValueError(
                f"Invalid class_map target for {source_cfg['name']}: "
                f"{source_name} -> {target_name}"
            )
    return mapping


def existing_roboflow_splits(source_dir: Path) -> dict[str, str]:
    """find the split folders present in a roboflow download."""
    # use only split folders that exist.
    splits = {}
    for source_split, target_split in ROBOFLOW_SPLIT_MAP.items():
        if (source_dir / source_split / "images").exists():
            splits[source_split] = target_split
    if not splits:
        raise FileNotFoundError(f"No Roboflow YOLO split folders found in {source_dir}")
    return splits


def list_images(images_dir: Path) -> list[Path]:
    """list image files in a split folder."""
    return sorted(path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)


def count_dict(counter: Counter) -> dict[str, int]:
    """convert a counter to a sorted string-key dict."""
    return {str(key): value for key, value in sorted(counter.items())}


def name_count_dict(counter: Counter) -> dict[str, int]:
    """convert a class-name counter to a sorted dict."""
    return {str(key): value for key, value in sorted(counter.items())}


def copy_roboflow_split(
    source_dir: Path,
    source_name: str,
    source_names: list[str],
    class_map: dict[str, str],
    custom_id_by_name: dict[str, int],
    coco_mapping: dict[int, dict],
    custom_dir: Path,
    baseline_dir: Path,
    source_split: str,
    target_split: str,
    expected_names: list[str],
) -> dict:
    """copy one roboflow split into the merged dataset views."""
    # copy each roboflow source into the merged dataset.
    images_dir = source_dir / source_split / "images"
    labels_dir = source_dir / source_split / "labels"
    images = list_images(images_dir)

    target_counts_by_id = Counter()
    target_counts_by_name = Counter()
    source_counts_by_name = Counter()
    empty_labels = 0
    copied = 0

    for source_image in images:
        label_path = labels_dir / source_image.with_suffix(".txt").name
        dest_name = f"{source_name}_{source_split}_{source_image.name}"

        # prefix names so sources cannot overwrite each other.
        dest_image_custom = custom_dir / "images" / target_split / dest_name
        dest_image_baseline = baseline_dir / "images" / target_split / dest_name
        shutil.copy2(source_image, dest_image_custom)
        shutil.copy2(source_image, dest_image_baseline)

        custom_label_lines: list[str] = []
        baseline_label_lines: list[str] = []
        raw_label_text = label_path.read_text(encoding="utf-8").splitlines() if label_path.exists() else []

        for raw_line in raw_label_text:
            if not raw_line.strip():
                continue
            source_id, coords = parse_yolo_label(raw_line, len(source_names) - 1)
            source_class_name = source_names[source_id]
            source_key = normalize_name(source_class_name)
            if source_key not in class_map:
                raise ValueError(
                    f"Missing class_map entry for {source_name} class {source_id}: "
                    f"{source_class_name}"
                )

            target_name = class_map[source_key]
            target_id = custom_id_by_name[normalize_name(target_name)]

            # count the source label and the merged label.
            source_counts_by_name[source_class_name] += 1
            target_counts_by_id[target_id] += 1
            target_counts_by_name[expected_names[target_id]] += 1
            custom_label_lines.append(" ".join([str(target_id), *coords]))

            coco_id = int(coco_mapping[target_id]["coco_id"])
            baseline_label_lines.append(" ".join([str(coco_id), *coords]))

        if not custom_label_lines:
            empty_labels += 1

        dest_label_name = Path(dest_name).with_suffix(".txt").name
        (custom_dir / "labels" / target_split / dest_label_name).write_text(
            "\n".join(custom_label_lines) + ("\n" if custom_label_lines else ""),
            encoding="utf-8",
        )
        (baseline_dir / "labels" / target_split / dest_label_name).write_text(
            "\n".join(baseline_label_lines) + ("\n" if baseline_label_lines else ""),
            encoding="utf-8",
        )
        copied += 1

    return {
        "images": copied,
        "empty_label_files": empty_labels,
        "objects_by_class_id": target_counts_by_id,
        "objects_by_class_name": target_counts_by_name,
        "source_objects_by_class_name": source_counts_by_name,
    }


def prepare_roboflow_merged(config_path: Path, force: bool) -> dict:
    """prepare the merged roboflow dataset used by the main experiment."""
    # main path for the merged roboflow experiment.
    root = project_root()
    config = load_yaml(config_path)
    dataset_cfg = config["dataset"]

    raw_root = resolve_path(dataset_cfg["raw_dir"], root)
    custom_dir = resolve_path(dataset_cfg["custom_dataset_dir"], root)
    baseline_dir = resolve_path(dataset_cfg["baseline_dataset_dir"], root)
    reports_dir = resolve_path(config["outputs"]["reports_dir"], root)

    expected_names = read_expected_names(config)
    # quick lookup from normalized class name to final class id.
    custom_id_by_name = {normalize_name(name): idx for idx, name in enumerate(expected_names)}
    coco_mapping = {int(k): v for k, v in dataset_cfg["baseline_coco_mapping"].items()}
    validate_coco_mapping(expected_names, coco_mapping)

    clean_dataset_dirs(custom_dir, baseline_dir, force=force)

    split_summary = {
        # keep empty splits so data.yaml stays stable.
        split: {
            "images": 0,
            "empty_label_files": 0,
            "objects_by_class_id": Counter(),
            "objects_by_class_name": Counter(),
            "sources": {},
        }
        for split in ["train", "val", "test"]
    }
    sources_summary = {}

    model_format = dataset_cfg.get("roboflow_format", "yolov8")
    raw_root.mkdir(parents=True, exist_ok=True)

    for source_cfg in dataset_cfg["sources"]:
        # download, validate, then copy into the merged views.
        source_name = normalize_name(source_cfg["name"])
        source_dir = download_roboflow_source(source_cfg, raw_root, model_format)
        source_names = validate_source_names(source_dir, source_cfg)
        class_map = normalized_class_map(source_cfg, expected_names)
        source_splits = existing_roboflow_splits(source_dir)

        sources_summary[source_name] = {
            "workspace": source_cfg["workspace"],
            "project": source_cfg["project"],
            "version": source_cfg["version"],
            "raw_dir": str(source_dir),
            "source_names": {str(i): name for i, name in enumerate(source_names)},
            "class_map": source_cfg["class_map"],
            "splits": {},
        }

        for source_split, target_split in source_splits.items():
            # one source split may map to train, val, or test in the final view.
            stats = copy_roboflow_split(
                source_dir=source_dir,
                source_name=source_name,
                source_names=source_names,
                class_map=class_map,
                custom_id_by_name=custom_id_by_name,
                coco_mapping=coco_mapping,
                custom_dir=custom_dir,
                baseline_dir=baseline_dir,
                source_split=source_split,
                target_split=target_split,
                expected_names=expected_names,
            )

            target_info = split_summary[target_split]
            target_info["images"] += stats["images"]
            target_info["empty_label_files"] += stats["empty_label_files"]
            target_info["objects_by_class_id"].update(stats["objects_by_class_id"])
            target_info["objects_by_class_name"].update(stats["objects_by_class_name"])
            target_info["sources"][source_name] = {
                "source_split": source_split,
                "images": stats["images"],
                "empty_label_files": stats["empty_label_files"],
                "objects_by_class_name": name_count_dict(stats["objects_by_class_name"]),
                "source_objects_by_class_name": name_count_dict(stats["source_objects_by_class_name"]),
            }
            sources_summary[source_name]["splits"][source_split] = {
                "target_split": target_split,
                "images": stats["images"],
                "empty_label_files": stats["empty_label_files"],
                "objects_by_class_name": name_count_dict(stats["objects_by_class_name"]),
                "source_objects_by_class_name": name_count_dict(stats["source_objects_by_class_name"]),
            }

    custom_yaml, baseline_yaml = write_data_yamls(custom_dir, baseline_dir, expected_names)

    final_split_summary = {}
    total_by_class = Counter()
    for split, info in split_summary.items():
        # convert counters before writing json.
        total_by_class.update(info["objects_by_class_name"])
        final_split_summary[split] = {
            "images": info["images"],
            "empty_label_files": info["empty_label_files"],
            "objects_by_class_id": count_dict(info["objects_by_class_id"]),
            "objects_by_class_name": name_count_dict(info["objects_by_class_name"]),
            "sources": info["sources"],
        }

    summary = {
        "source_type": dataset_cfg["source_type"],
        "roboflow_format": model_format,
        "raw_dir": str(raw_root),
        "custom_dataset_yaml": str(custom_yaml),
        "baseline_coco_dataset_yaml": str(baseline_yaml),
        "custom_names": {str(i): name for i, name in enumerate(expected_names)},
        "baseline_coco_mapping": dataset_cfg["baseline_coco_mapping"],
        "source_datasets": sources_summary,
        "splits": final_split_summary,
        "total_objects_by_class": name_count_dict(total_by_class),
    }

    summary_path = reports_dir / "dataset_summary.json"
    write_json(summary_path, summary)

    print("merged roboflow dataset ready")
    print(f"custom yaml: {custom_yaml}")
    print(f"baseline yaml: {baseline_yaml}")
    print(f"summary: {summary_path}")
    return summary


def prepare(config_path: Path, force: bool) -> dict:
    """prepare the dataset described by a pipeline config."""
    root = project_root()
    config = load_yaml(config_path)
    dataset_cfg = config["dataset"]

    # keep the older danielhfnr path for comparison.
    source_type = dataset_cfg.get("source_type", "danielhfnr_git")
    if source_type == "roboflow_merged":
        return prepare_roboflow_merged(config_path, force=force)
    if source_type != "danielhfnr_git":
        raise ValueError(f"Unsupported dataset source_type: {source_type}")

    raw_dir = resolve_path(dataset_cfg["raw_dir"], root)
    custom_dir = resolve_path(dataset_cfg["custom_dataset_dir"], root)
    baseline_dir = resolve_path(dataset_cfg["baseline_dataset_dir"], root)
    reports_dir = resolve_path(config["outputs"]["reports_dir"], root)

    clone_dataset(dataset_cfg["repo_url"], dataset_cfg.get("repo_branch", "master"), raw_dir)

    expected_names = read_expected_names(config)
    validate_dataset_names(raw_dir, expected_names)

    label_root = find_label_root(raw_dir)
    clean_dataset_dirs(custom_dir, baseline_dir, force=force)

    coco_mapping = {int(k): v for k, v in dataset_cfg["baseline_coco_mapping"].items()}
    split_summary = {}
    for split, filename in SPLIT_FILES.items():
        split_file = raw_dir / filename
        if not split_file.exists():
            raise FileNotFoundError(f"Missing split file: {split_file}")
        split_summary[split] = copy_split(
            raw_dir=raw_dir,
            label_root=label_root,
            custom_dir=custom_dir,
            baseline_dir=baseline_dir,
            split=split,
            split_file=split_file,
            expected_names=expected_names,
            coco_mapping=coco_mapping,
        )

    custom_yaml, baseline_yaml = write_data_yamls(custom_dir, baseline_dir, expected_names)

    total_by_class = defaultdict(int)
    for split_info in split_summary.values():
        for name, count in split_info["objects_by_class_name"].items():
            total_by_class[name] += count

    summary = {
        "source_repo": dataset_cfg["repo_url"],
        "raw_dir": str(raw_dir),
        "custom_dataset_yaml": str(custom_yaml),
        "baseline_coco_dataset_yaml": str(baseline_yaml),
        "custom_names": {str(i): name for i, name in enumerate(expected_names)},
        "baseline_coco_mapping": dataset_cfg["baseline_coco_mapping"],
        "splits": split_summary,
        "total_objects_by_class": dict(sorted(total_by_class.items())),
    }

    summary_path = reports_dir / "dataset_summary.json"
    write_json(summary_path, summary)

    print("dataset ready")
    print(f"custom yaml: {custom_yaml}")
    print(f"baseline yaml: {baseline_yaml}")
    print(f"summary: {summary_path}")
    return summary


def main() -> None:
    """command-line entry point for dataset preparation."""
    parser = argparse.ArgumentParser(description="Prepare a CARLA dataset for fine tuning.")
    parser.add_argument("--config", default="configs/danielhfnr_yolo11s.yaml", help="Path to pipeline config YAML.")
    parser.add_argument("--force", action="store_true", help="Rebuild prepared datasets if they already exist.")
    args = parser.parse_args()

    prepare(resolve_path(args.config, project_root()), force=args.force)


if __name__ == "__main__":
    main()
