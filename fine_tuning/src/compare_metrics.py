from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import load_json, load_yaml, project_root, resolve_path


def metric_row(label: str, result: dict) -> dict:
    """make one compact row from an evaluation json."""
    # keep the summary table compact.
    metrics = result["metrics"]
    return {
        "model": label,
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "map50": metrics.get("map50"),
        "map50_95": metrics.get("map50_95"),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    """write a list of dict rows to csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def compare(args: argparse.Namespace) -> dict:
    """compare baseline and fine-tuned metric files."""
    config = load_yaml(resolve_path(args.config, project_root()))
    baseline = load_json(resolve_path(args.baseline_json, project_root()))
    finetuned = load_json(resolve_path(args.finetuned_json, project_root()))
    reports_dir = resolve_path(args.reports_dir or config["outputs"]["reports_dir"], project_root())
    comparison_cfg = config.get("comparison", {})

    # one row for the baseline, one for the trained model.
    rows = [
        metric_row(comparison_cfg.get("baseline_label", "pretrained_yolo11s_coco_mapped"), baseline),
        metric_row(comparison_cfg.get("finetuned_label", "finetuned_yolo11s_custom5"), finetuned),
    ]
    overall_csv = reports_dir / "metrics_comparison.csv"
    write_csv(overall_csv, rows)

    # the per-class file helps find weak classes.
    mapping = {int(k): v for k, v in config["dataset"]["baseline_coco_mapping"].items()}
    per_class_rows = []
    for custom_id, map_info in sorted(mapping.items()):
        # baseline names use coco; fine-tuned names use our labels.
        custom_name = map_info["custom_name"]
        baseline_name = map_info["coco_name"]
        baseline_ap50 = baseline.get("per_class", {}).get(baseline_name, {}).get("ap50")
        finetuned_ap50 = finetuned.get("per_class", {}).get(custom_name, {}).get("ap50")
        delta = None
        if baseline_ap50 is not None and finetuned_ap50 is not None:
            delta = finetuned_ap50 - baseline_ap50
        per_class_rows.append(
            {
                "custom_class": custom_name,
                "baseline_coco_class": baseline_name,
                "baseline_ap50": baseline_ap50,
                "finetuned_ap50": finetuned_ap50,
                "delta_ap50": delta,
                "mapping_note": map_info.get("note", ""),
            }
        )

    per_class_csv = reports_dir / "per_class_ap50_comparison.csv"
    write_csv(per_class_csv, per_class_rows)

    print("comparison complete")
    print(f"overall: {overall_csv}")
    print(f"per class: {per_class_csv}")
    return {"overall_csv": str(overall_csv), "per_class_csv": str(per_class_csv)}


def main() -> None:
    """command-line entry point for metric comparison."""
    parser = argparse.ArgumentParser(description="Compare baseline and fine-tuned YOLO metrics.")
    parser.add_argument("--config", default="configs/danielhfnr_yolo11s.yaml")
    parser.add_argument("--baseline-json", required=True)
    parser.add_argument("--finetuned-json", required=True)
    parser.add_argument("--reports-dir", default=None)
    args = parser.parse_args()
    compare(args)


if __name__ == "__main__":
    main()
