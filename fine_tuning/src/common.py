from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


PLOT_ARTIFACT_PATTERNS = [
    "*.png",
    "labels*.jpg",
    "train_batch*.jpg",
    "val_batch*.jpg",
]


# used only for the baseline dataset view.
COCO80_NAMES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]


def project_root() -> Path:
    """return the fine_tuning folder."""
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path, root: Path | None = None) -> Path:
    """resolve pipeline paths relative to fine_tuning."""
    # notebook paths usually start from fine_tuning/.
    path = Path(value)
    if path.is_absolute():
        return path
    return (root or project_root()) / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    """load a yaml config file."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    """write yaml while keeping key order readable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    """write a json report or summary file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def load_json(path: str | Path) -> dict[str, Any]:
    """load a json report file."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def names_from_yaml(data_yaml: str | Path) -> dict[int, str]:
    """read class id to name mapping from an ultralytics data.yaml."""
    # ultralytics accepts either a list or an id:name mapping.
    data = load_yaml(data_yaml)
    names = data["names"]
    if isinstance(names, list):
        return {idx: name for idx, name in enumerate(names)}
    return {int(idx): name for idx, name in names.items()}


def as_float(value: Any) -> float | None:
    """convert metric values to plain floats when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int_list(value: str | None) -> list[int] | None:
    """parse comma-separated class ids from the cli."""
    if value is None or value.strip() == "":
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def remove_plot_artifacts(run_dir: str | Path) -> None:
    """remove large default ultralytics plots from a run folder."""
    if not str(run_dir).strip():
        return

    run_path = Path(run_dir)
    if not run_path.exists():
        return

    # keep weights and csv files, drop the extra plots.
    for pattern in PLOT_ARTIFACT_PATTERNS:
        for path in run_path.glob(pattern):
            if path.is_file():
                path.unlink()
