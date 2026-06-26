from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pid_controller import LongitudinalPID, command_to_actuation


class LongitudinalPIDTests(unittest.TestCase):
    def make_controller(self, **overrides: float) -> LongitudinalPID:
        values = {
            "kp": 0.15,
            "ki": 0.01,
            "kd": 0.02,
            "integral_limit": 10.0,
            "derivative_smoothing": 0.5,
        }
        values.update(overrides)
        return LongitudinalPID(**values)

    def test_positive_error_requests_throttle(self) -> None:
        command = self.make_controller().update(20.0, 0.0, 0.05)
        self.assertGreater(command, 0.0)
        self.assertLessEqual(command, 1.0)

    def test_negative_error_requests_brake(self) -> None:
        command = self.make_controller().update(0.0, 10.0, 0.05)
        self.assertLess(command, 0.0)
        self.assertGreaterEqual(command, -1.0)

    def test_integral_does_not_grow_while_saturated(self) -> None:
        controller = self.make_controller(kp=1.0, ki=1.0, kd=0.0)
        for _ in range(20):
            controller.update(100.0, 0.0, 0.1)
        self.assertEqual(controller.integral, 0.0)

    def test_reset_clears_controller_state(self) -> None:
        controller = self.make_controller(kp=0.0, ki=1.0, kd=0.0)
        controller.update(1.0, 0.0, 0.1)
        self.assertGreater(controller.integral, 0.0)
        controller.reset()
        self.assertEqual(controller.integral, 0.0)
        self.assertIsNone(controller.previous_error)

    def test_actuation_is_mutually_exclusive(self) -> None:
        throttle, brake = command_to_actuation(0.5, 0.75, 0.8)
        self.assertAlmostEqual(throttle, 0.375)
        self.assertEqual(brake, 0.0)

        throttle, brake = command_to_actuation(-0.5, 0.75, 0.8)
        self.assertEqual(throttle, 0.0)
        self.assertAlmostEqual(brake, 0.4)

    def test_invalid_dt_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_controller().update(20.0, 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
