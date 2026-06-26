from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from common import load_yaml
from run_pid_speed import _build_summary


class RunSummaryTests(unittest.TestCase):
    def test_ideal_telemetry_passes_acceptance(self) -> None:
        config = load_yaml(PROJECT_ROOT / "configs" / "pid_speed.yaml")
        telemetry = []
        frame = 1
        for elapsed, target in (
            (2.0, 20.0),
            (3.0, 20.0),
            (9.0, 10.0),
            (10.0, 10.0),
            (20.0, 0.0),
        ):
            telemetry.append(
                {
                    "frame": frame,
                    "time_seconds": elapsed,
                    "target_speed_kmh": target,
                    "speed_kmh": target,
                    "speed_error_kmh": 0.0,
                    "pid_command": 0.0,
                    "throttle": 0.0,
                    "brake": 0.0,
                    "steer": 0.0,
                    "location_x": 0.0,
                    "location_y": 0.0,
                    "location_z": 0.0,
                }
            )
            frame += 1

        summary = _build_summary(
            config=config,
            telemetry=telemetry,
            completed=True,
            failure=None,
            run_dir=PROJECT_ROOT / "workspace" / "runs" / "test",
            map_name="Carla/Maps/Town10HD_Opt",
            spawn_index=0,
        )

        self.assertTrue(summary["acceptance"]["passed"])
        self.assertFalse(summary["simultaneous_throttle_brake"])


if __name__ == "__main__":
    unittest.main()
