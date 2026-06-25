from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from common import project_root, resolve_path, write_json


def choose_images(source_dir: Path, count: int, seed: int) -> list[Path]:
    """pick a stable image sample for visual comparison."""
    # fixed seed keeps model samples comparable.
    images = sorted(
        [
            *source_dir.glob("*.jpg"),
            *source_dir.glob("*.jpeg"),
            *source_dir.glob("*.png"),
        ]
    )
    if not images:
        raise FileNotFoundError(f"No images found in {source_dir}")
    rng = random.Random(seed)
    if len(images) <= count:
        return images
    # sort again so the copied files are in a stable order.
    return sorted(rng.sample(images, count))


def predict(args: argparse.Namespace) -> dict:
    """run yolo prediction on a small sample and save images."""
    from ultralytics import YOLO

    source_dir = resolve_path(args.source_dir, project_root())
    project = resolve_path(args.project, project_root())
    output_json = resolve_path(args.output_json, project_root()) if args.output_json else None
    selected_dir = project / args.name / "selected_source_images"
    selected_dir.mkdir(parents=True, exist_ok=True)

    # copy the sample first so models see the same images.
    selected = choose_images(source_dir, args.count, args.seed)
    for image in selected:
        shutil.copy2(image, selected_dir / image.name)

    model = YOLO(args.model)
    # keep these visual outputs for quick inspection.
    results = model.predict(
        source=str(selected_dir),
        imgsz=args.imgsz,
        conf=args.conf,
        device=args.device,
        project=str(project),
        name=args.name,
        save=True,
        exist_ok=True,
        verbose=True,
    )

    save_dir = getattr(results[0], "save_dir", None) if results else project / args.name
    if output_json:
        summary = {
            "model": args.model,
            "source_dir": str(source_dir),
            "selected_images": [str(path) for path in selected],
            "prediction_dir": str(save_dir),
        }
        write_json(output_json, summary)

    print(f"samples saved: {save_dir}")
    return {"prediction_dir": str(save_dir)}


def main() -> None:
    """command-line entry point for sample predictions."""
    parser = argparse.ArgumentParser(description="Run YOLO predictions on a small image sample.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--device", default="0")
    parser.add_argument("--project", default="workspace/runs/predictions")
    parser.add_argument("--name", default="sample_predictions")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()
    predict(args)


if __name__ == "__main__":
    main()
