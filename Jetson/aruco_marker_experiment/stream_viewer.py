#!/usr/bin/env python3
"""First test: display phone video and show which gyro axis changes."""

from __future__ import annotations

import argparse
import time

import cv2

from sensor_server import SensorServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--frame-flip-code",
        type=int,
        choices=(-1, 0, 1),
        default=-1,
        help="Correct camera orientation: -1=rotate 180, 0=vertical flip, 1=horizontal flip",
    )
    parser.add_argument("--no-frame-flip", action="store_true")
    args = parser.parse_args()

    frame_flip_code = None if args.no_frame_flip else args.frame_flip_code
    server = SensorServer(port=args.port, frame_flip_code=frame_flip_code)
    server.start()
    print("Start the Android app. Press Q to quit.")
    if not server.wait_for_client(60.0):
        raise SystemExit("No phone connected")

    last_print = 0.0
    try:
        while True:
            frame, _ = server.get_frame()
            gyro = server.get_gyro()
            if gyro and time.monotonic() - last_print > 0.25:
                print(
                    "gyro rad/s  x={:+.3f}  y={:+.3f}  z={:+.3f}".format(*gyro.values)
                )
                last_print = time.monotonic()
            if frame is not None:
                cv2.imshow("Phone grayscale stream", frame)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
            time.sleep(0.005)
    finally:
        server.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
