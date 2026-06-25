from __future__ import annotations

import argparse
from pathlib import Path

from common import as_float, names_from_yaml, parse_int_list, project_root, remove_plot_artifacts, resolve_path, write_json


def to_list(value):
    """convert tensors and arrays to normal python lists."""
    if value is None:
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def per_class_ap(metrics, data_yaml: Path) -> dict[str, dict[str, float | None]]:
    """extract per-class ap values from an ultralytics metrics object."""
    # ultralytics reports per-class values by class index.
    names = names_from_yaml(data_yaml)
    box = metrics.box
    ap50_values = to_list(getattr(box, "ap50", None))
    ap5095_values = to_list(getattr(box, "ap", None))
    class_indices = to_list(getattr(box, "ap_class_index", None))

    if ap50_values is None:
        return {}
    if class_indices is None:
        # older metric objects may omit the class index list.
        class_indices = list(range(len(ap50_values)))

    result = {}
    for pos, class_id in enumerate(class_indices):
        class_id = int(class_id)
        class_name = names.get(class_id, f"class_{class_id}")
        result[class_name] = {
            "class_id": class_id,
            "ap50": as_float(ap50_values[pos]) if pos < len(ap50_values) else None,
            "map50_95": as_float(ap5095_values[pos]) if ap5095_values is not None and pos < len(ap5095_values) else None,
        }
    return result


def evaluate(args: argparse.Namespace) -> dict:
    """evaluate one yolo model and save metrics as json."""
    # delay the import so report helpers can run without a gpu setup.
    from ultralytics import YOLO

    data_yaml = resolve_path(args.data, project_root())
    project = resolve_path(args.project, project_root())
    output_json = resolve_path(args.output_json, project_root())
    classes = parse_int_list(args.classes)

    # the class filter is only used for the coco baseline comparison.
    model = YOLO(args.model)
    # keep validation folders small; this script writes the reports.
    metrics = model.val(
        data=str(data_yaml),
        split=args.split,
        imgsz=args.imgsz,
        device=args.device,
        project=str(project),
        name=args.name,
        classes=classes,
        conf=args.conf,
        iou=args.iou,
        plots=False,
        save_json=False,
        verbose=True,
    )
    save_dir = str(getattr(metrics, "save_dir", ""))

    summary = {
        "label_space": args.label_space,
        "model": args.model,
        "data_yaml": str(data_yaml),
        "split": args.split,
        "image_size": args.imgsz,
        "class_filter": classes,
        "save_dir": save_dir,
        "metrics": {
            "precision": as_float(getattr(metrics.box, "mp", None)),
            "recall": as_float(getattr(metrics.box, "mr", None)),
            "map50": as_float(getattr(metrics.box, "map50", None)),
            "map50_95": as_float(getattr(metrics.box, "map", None)),
        },
        "per_class": per_class_ap(metrics, data_yaml),
    }
    remove_plot_artifacts(save_dir)
    write_json(output_json, summary)

    print("evaluation complete")
    print(
        f"map50={summary['metrics']['map50']} "
        f"map50_95={summary['metrics']['map50_95']}"
    )
    return summary


def main() -> None:
    """command-line entry point for evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate YOLO model and save metrics as JSON.")
    parser.add_argument("--model", required=True, help="Model path/name")
    parser.add_argument("--data", required=True, help="Dataset data.yaml path.")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"], help="Dataset split to evaluate.")
    parser.add_argument("--imgsz", type=int, default=640, help="Evaluation image size.")
    parser.add_argument("--device", default="0", help="Ultralytics device.")
    parser.add_argument("--project", default="workspace/internal/runs", help="YOLO output project folder.")
    parser.add_argument("--name", default="eval", help="YOLO run name.")
    parser.add_argument("--classes", default=None, help="comma separated class filter.")
    parser.add_argument("--conf", type=float, default=0.001, help="Validation confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.6, help="Validation IoU threshold.")
    parser.add_argument("--label-space", default="custom", help="True label for this evaluation result.")
    parser.add_argument("--output-json", required=True, help="metrics json location.")
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()
