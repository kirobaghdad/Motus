from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from common import load_yaml, target_speed_at, validate_pid_config


class CommonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = PROJECT_ROOT / "configs" / "pid_speed.yaml"
        self.config = load_yaml(self.config_path)

    def test_project_config_is_valid(self) -> None:
        validate_pid_config(self.config)

    def test_speed_profile_boundaries(self) -> None:
        profile = self.config["control"]["speed_profile"]
        self.assertEqual(target_speed_at(profile, 0.0), 20.0)
        self.assertEqual(target_speed_at(profile, 6.99), 20.0)
        self.assertEqual(target_speed_at(profile, 7.0), 10.0)
        self.assertEqual(target_speed_at(profile, 12.0), 0.0)

    def test_historical_files_are_present(self) -> None:
        required = [
            PROJECT_ROOT / "CARLA_controller.ipynb",
            PROJECT_ROOT / "sensor_data_20260311_082005.csv",
            PROJECT_ROOT / "sensor_data_20260311_082035.csv",
            PROJECT_ROOT.parent
            / "carla_yolo_integration"
            / "5_unified_live_detection.ipynb",
        ]
        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
