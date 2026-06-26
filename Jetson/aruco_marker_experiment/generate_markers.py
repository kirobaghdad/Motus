#!/usr/bin/env python3
"""Generate printable ArUco marker PNG files."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+", type=int, help="Marker IDs, for example: 0 1 2 3")
    parser.add_argument("--pixels", type=int, default=1200)
    parser.add_argument("--margin", type=int, default=120)
    parser.add_argument("--output", default="generated_markers")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    for marker_id in args.ids:
        if not 0 <= marker_id < 50:
            raise SystemExit("DICT_4X4_50 supports IDs 0 to 49")

        if hasattr(cv2.aruco, "generateImageMarker"):
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, args.pixels)
        else:
            marker = np.zeros((args.pixels, args.pixels), dtype=np.uint8)
            cv2.aruco.drawMarker(dictionary, marker_id, args.pixels, marker, 1)

        canvas = np.full(
            (args.pixels + 2 * args.margin, args.pixels + 2 * args.margin),
            255,
            dtype=np.uint8,
        )
        canvas[args.margin:-args.margin, args.margin:-args.margin] = marker
        filename = output / f"aruco_4x4_50_id_{marker_id}.png"
        cv2.imwrite(str(filename), canvas)
        print(filename)


if __name__ == "__main__":
    main()
