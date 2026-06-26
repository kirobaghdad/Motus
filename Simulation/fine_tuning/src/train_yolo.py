from __future__ import annotations

import argparse
from pathlib import Path

from common import project_root, remove_plot_artifacts, resolve_path, write_json


def train(args: argparse.Namespace) -> dict:
    """fine-tune a yolo model and save a small training summary."""
    # delay the import so config checks can run without ultralytics.
    from ultralytics import YOLO

    data_yaml = resolve_path(args.data, project_root())
    project = resolve_path(args.project, project_root())
    output_json = resolve_path(args.output_json, project_root())

    model = YOLO(args.model)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(project),
        name=args.name,
        patience=args.patience,
        seed=args.seed,
        workers=args.workers,
        optimizer=args.optimizer,
        pretrained=True,
        plots=False,  # sample images are made separately.
        save=True,
        verbose=True,
    )

    save_dir = getattr(results, "save_dir", None)
    if save_dir is None and getattr(model, "trainer", None) is not None:
        # ultralytics stores the path in slightly different places by version.
        save_dir = getattr(model.trainer, "save_dir", None)
    save_dir = Path(save_dir) if save_dir is not None else project / args.name
    remove_plot_artifacts(save_dir)

    # save the paths needed by the export step.
    best_model = save_dir / "weights" / "best.pt"
    last_model = save_dir / "weights" / "last.pt"
    summary = {
        "base_model": args.model,
        "data_yaml": str(data_yaml),
        "epochs": args.epochs,
        "image_size": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "save_dir": str(save_dir),
        "best_model": str(best_model),
        "last_model": str(last_model),
        "best_model_exists": best_model.exists(),
        "last_model_exists": last_model.exists(),
    }
    write_json(output_json, summary)

    print("training complete")
    print(f"run: {save_dir}")
    print(f"best: {best_model}")
    return summary


def main() -> None:
    """command-line entry point for training."""
    parser = argparse.ArgumentParser(description="Fine-tune YOLO on custom CARLA dataset.")
    parser.add_argument("--model", default="yolo11s.pt", help="Starting model.")
    parser.add_argument("--data", required=True, help="Custom dataset data.yaml path.")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--project", default="workspace/internal/runs")
    parser.add_argument("--name", default="finetune_yolo11s_custom5")
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--optimizer", default="auto")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
