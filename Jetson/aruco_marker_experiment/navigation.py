#!/usr/bin/env python3
"""Marker-assisted navigation using phone video and phone gyroscope."""

from __future__ import annotations

import argparse
import json
import math
import select
import signal
import sys
import termios
import time
import tty
from typing import Any

import cv2
import numpy as np

from motor_driver import ConsoleMotorDriver, JetsonGpioMotorDriver, clamp
from sensor_server import SensorServer


def wrap_degrees(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def angle_error(target: float, current: float) -> float:
    return wrap_degrees(target - current)


class GyroHeading:
    def __init__(self, axis: int, sign: float) -> None:
        self.axis = axis
        self.sign = sign
        self.heading_deg = 0.0
        self.last_timestamp_ns: int | None = None

    def update(self, timestamp_ns: int, values: tuple[float, ...]) -> None:
        if self.last_timestamp_ns is not None:
            dt = (timestamp_ns - self.last_timestamp_ns) / 1_000_000_000.0
            if 0.0 < dt < 0.2:
                radians_per_second = values[self.axis] * self.sign
                self.heading_deg = wrap_degrees(
                    self.heading_deg + math.degrees(radians_per_second * dt)
                )
        self.last_timestamp_ns = timestamp_ns


class MarkerDetector:
    def __init__(self) -> None:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self._new_api = hasattr(cv2.aruco, "ArucoDetector")
        if self._new_api:
            parameters = cv2.aruco.DetectorParameters()
            self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)
        else:
            parameters = cv2.aruco.DetectorParameters_create()
            self._dictionary = dictionary
            self._parameters = parameters

    def detect(self, gray: np.ndarray) -> list[dict[str, Any]]:
        if self._new_api:
            corners, ids, _ = self._detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray,
                self._dictionary,
                parameters=self._parameters,
            )

        results: list[dict[str, Any]] = []
        if ids is None:
            return results

        image_area = float(gray.shape[0] * gray.shape[1])
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            points = marker_corners.reshape(4, 2)
            center = points.mean(axis=0)
            area_ratio = abs(cv2.contourArea(points.astype(np.float32))) / image_area
            results.append(
                {
                    "id": int(marker_id),
                    "corners": points,
                    "center_x": float(center[0]),
                    "center_y": float(center[1]),
                    "area_ratio": area_ratio,
                }
            )
        return results


class KeyboardController:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled and sys.stdin.isatty()
        self._old_settings: list[Any] | None = None

    def __enter__(self) -> "KeyboardController":
        if self.enabled:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if self.enabled and self._old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)

    def read_key(self) -> str | None:
        if not self.enabled:
            return None
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        return sys.stdin.read(1).lower()


class Navigator:
    def __init__(
        self,
        config: dict[str, Any],
        route: list[dict[str, Any]],
        use_gpio: bool,
        autostart: bool = False,
    ) -> None:
        self.config = config
        self.route = route
        camera_config = config.get("camera", {})
        self.server = SensorServer(
            port=int(config["network"]["port"]),
            frame_flip_code=camera_config.get("frame_flip_code"),
        )
        self.detector = MarkerDetector()
        self.heading = GyroHeading(
            axis=int(config["imu"]["gyro_axis"]),
            sign=float(config["imu"]["gyro_sign"]),
        )
        self.control = config.get("control", {})

        self.use_gpio = use_gpio
        self.motor = ConsoleMotorDriver()

        self.state = "WAIT_START"
        self.route_index = 0
        self.target_heading = 0.0
        self.turn_target = 0.0
        self.turn_start_heading = 0.0
        self.segment_started = time.monotonic()
        self.last_gyro_timestamp = 0
        self.gyro_sample_count = 0
        self.last_gyro_values: tuple[float, ...] | None = None
        self.last_frame_timestamp = 0
        self.last_new_frame_time = time.monotonic()
        self.last_new_gyro_time = time.monotonic()
        self.running = True
        self.movement_enabled = False
        self.speed_scale = float(self.control.get("speed_scale", 1.0))
        self.speed_step = float(self.control.get("speed_step", 0.05))
        self.min_speed_scale = float(self.control.get("min_speed_scale", 0.10))
        self.max_speed_scale = float(self.control.get("max_speed_scale", 1.00))
        keyboard_config = config.get("keyboard", {})
        self.start_key = str(keyboard_config.get("start_key", "s")).lower()
        self.restart_key = str(keyboard_config.get("restart_key", "r")).lower()
        self.quit_key = str(keyboard_config.get("quit_key", "q")).lower()
        self.speed_up_key = str(keyboard_config.get("speed_up_key", "+")).lower()
        self.speed_down_key = str(keyboard_config.get("speed_down_key", "-")).lower()
        self.gyro_axis_key = str(keyboard_config.get("gyro_axis_key", "g")).lower()
        self._reset_navigation(armed=autostart)

    def run(self, headless: bool = False) -> None:
        self.server.start()
        try:
            print("Start the Android app now.")
            wait_started = time.monotonic()
            while self.running and not self.server.wait_for_client(timeout=0.1):
                if time.monotonic() - wait_started >= 60.0:
                    raise RuntimeError("No phone connected within 60 seconds")
            if not self.running:
                return

            now = time.monotonic()
            self.last_new_frame_time = now
            self.last_new_gyro_time = now
            control_period = 1.0 / float(self.control["frequency_hz"])
            with KeyboardController(enabled=True) as keyboard:
                print(
                    f"Controls: '{self.start_key}' start, "
                    f"'{self.restart_key}' restart, "
                    f"'{self.speed_down_key}/{self.speed_up_key}' speed, "
                    f"'{self.gyro_axis_key}' gyro axis, '{self.quit_key}' quit"
                )
                if self.movement_enabled:
                    print("Navigation armed. Waiting for start marker.")
                elif keyboard.enabled:
                    print(f"Navigation is not armed. Press '{self.start_key}' to start.")
                else:
                    print(
                        "Navigation is not armed and no keyboard is attached. "
                        "Restart with --autostart or run interactively and press "
                        f"'{self.start_key}'."
                    )
                while self.running:
                    loop_start = time.monotonic()
                    key = keyboard.read_key()
                    if key is not None:
                        self._handle_key(key)

                    self._update_gyro()
                    frame, frame_timestamp = self.server.get_frame()

                    if self.server.error:
                        raise RuntimeError(self.server.error)

                    now = time.monotonic()
                    if frame_timestamp and frame_timestamp != self.last_frame_timestamp:
                        self.last_frame_timestamp = frame_timestamp
                        self.last_new_frame_time = now
                    if now - self.last_new_frame_time > 1.5:
                        self.motor.stop()
                        raise RuntimeError("Camera stream is stale")
                    if now - self.last_new_gyro_time > 1.5:
                        self.motor.stop()
                        raise RuntimeError("Gyroscope stream is stale")

                    if frame is not None:
                        markers = self.detector.detect(frame)
                        self._control(markers, frame.shape[1])
                        if not headless:
                            display = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                            self._draw_debug(display, markers)
                            try:
                                cv2.imshow("Marker IMU Robot", display)
                                cv_key = cv2.waitKey(1) & 0xFF
                                if cv_key != 255:
                                    self._handle_key(chr(cv_key).lower() if cv_key < 128 else "")
                            except cv2.error as e:
                                print(f"\n[Warning] Display error (no GUI available?). Switching to headless mode. ({e})\n")
                                headless = True

                    elapsed = time.monotonic() - loop_start
                    time.sleep(max(0.0, control_period - elapsed))
        finally:
            self.motor.close()
            self.server.close()
            cv2.destroyAllWindows()

    def _reset_navigation(self, armed: bool) -> None:
        if armed:
            self._ensure_motor_ready()
        self.movement_enabled = armed
        self.motor.set_armed(armed)
        self.state = "WAIT_START" if armed else "WAIT_KEY"
        self.route_index = 0
        self.target_heading = self.heading.heading_deg
        self.turn_target = self.heading.heading_deg
        self.turn_start_heading = self.heading.heading_deg
        self.segment_started = time.monotonic()
        self.motor.stop()

    def _ensure_motor_ready(self) -> None:
        if self.use_gpio and not isinstance(self.motor, JetsonGpioMotorDriver):
            self.motor.close()
            self.motor = JetsonGpioMotorDriver(**self.config["gpio"])

    def _disarm(self, state: str = "STOPPED") -> None:
        self.state = state
        self.movement_enabled = False
        self.motor.set_armed(False)
        self.motor.stop()

    def request_stop(self) -> None:
        self.running = False
        self._disarm()

    def _handle_key(self, key: str) -> None:
        if key == self.quit_key or key in ("\x03", "\x1b"):
            self.request_stop()
            return

        if key == self.start_key:
            if self.state in ("WAIT_KEY", "STOPPED"):
                self._reset_navigation(armed=True)
                print("Navigation started. Waiting for start marker.")
            return

        if key == self.restart_key:
            self._reset_navigation(armed=True)
            print("Navigation restarted from the first marker.")
            return

        if key == self.speed_up_key:
            self._adjust_speed(self.speed_step)
            return

        if key == self.speed_down_key:
            self._adjust_speed(-self.speed_step)
            return

        if key == self.gyro_axis_key:
            self.heading.axis = (self.heading.axis + 1) % 3
            self.heading.heading_deg = 0.0
            self.heading.last_timestamp_ns = None
            self.target_heading = 0.0
            self.turn_target = 0.0
            print(f"Gyro axis changed to {self.heading.axis}; heading reset to 0.")

    def _adjust_speed(self, delta: float) -> None:
        self.speed_scale = clamp(
            self.speed_scale + delta,
            self.min_speed_scale,
            self.max_speed_scale,
        )
        print(f"Speed scale set to {self.speed_scale:.2f}")

    def _update_gyro(self) -> None:
        sample = self.server.get_gyro()
        if sample and sample.timestamp_ns != self.last_gyro_timestamp:
            self.heading.update(sample.timestamp_ns, sample.values)
            self.last_gyro_timestamp = sample.timestamp_ns
            self.gyro_sample_count += 1
            self.last_gyro_values = sample.values
            self.last_new_gyro_time = time.monotonic()

    def _control(self, markers: list[dict[str, Any]], image_width: int) -> None:
        if self.state == "WAIT_KEY":
            self.motor.stop()
            return

        if not self.route or self.state == "STOPPED" or self.route_index >= len(self.route):
            self._disarm()
            return

        expected = self.route[self.route_index]
        expected_marker = next((m for m in markers if m["id"] == int(expected["id"])), None)

        if self.state == "WAIT_START":
            self.motor.stop()
            if expected_marker is not None:
                print(f"Start marker {expected['id']} found")
                self.target_heading = self.heading.heading_deg
                self._advance_route()
                self.state = "DRIVE" if self.route_index < len(self.route) else "STOPPED"
                self.segment_started = time.monotonic()
            return

        if self.state == "TURN":
            error = angle_error(self.turn_target, self.heading.heading_deg)
            tolerance = float(self.control["turn_tolerance_deg"])
            if abs(error) <= tolerance:
                self.motor.stop()
                self.target_heading = self.turn_target
                self.state = "DRIVE"
                self.segment_started = time.monotonic()
                print(f"Turn complete. Heading={self.heading.heading_deg:.1f} deg")
                return

            turn_elapsed = time.monotonic() - self.segment_started
            turn_timeout = float(
                self.control.get(
                    "turn_timeout_s",
                    self.control.get("segment_timeout_s", 18.0),
                )
            )
            if turn_elapsed > turn_timeout:
                print("Turn did not complete before timeout. Stopping.")
                self._disarm()
                return

            if expected_marker is not None:
                self.motor.stop()
                self.target_heading = self.heading.heading_deg
                self.state = "DRIVE"
                self.segment_started = time.monotonic()
                print(
                    f"Turn complete by sighting marker {expected['id']}. "
                    f"Heading={self.heading.heading_deg:.1f} deg"
                )
                return

            steering = clamp(float(self.control["turn_kp"]) * error)
            throttle = self._scaled_throttle(float(self.control["turn_throttle"]))
            self._set_drive(throttle, steering)
            return

        # DRIVE state.
        if time.monotonic() - self.segment_started > float(self.control["segment_timeout_s"]):
            print("Expected marker was not found before timeout. Stopping.")
            self._disarm()
            return

        marker_steering = 0.0
        if expected_marker is not None:
            normalized_x = (expected_marker["center_x"] - image_width / 2.0) / (image_width / 2.0)
            # Internal convention: positive steering means left.
            marker_steering = -float(self.control["marker_kp"]) * normalized_x

            if expected_marker["area_ratio"] >= float(self.control["marker_trigger_area_ratio"]):
                self._execute_waypoint(expected)
                return

        heading_err = angle_error(self.target_heading, self.heading.heading_deg)
        heading_steering = float(self.control["heading_kp"]) * heading_err
        steering = clamp(marker_steering + heading_steering)
        throttle = self._scaled_throttle(float(self.control["forward_throttle"]))
        self._set_drive(throttle, steering)

    def _scaled_throttle(self, throttle: float) -> float:
        return clamp(throttle * self.speed_scale)

    def _set_drive(self, throttle: float, steering: float) -> None:
        if not self.movement_enabled:
            self.motor.stop()
            return
        self.motor.set_drive(throttle, steering)

    def _execute_waypoint(self, waypoint: dict[str, Any]) -> None:
        action = str(waypoint.get("action", "straight"))
        marker_id = waypoint["id"]
        print(f"Reached marker {marker_id}; action={action}")

        if action == "stop":
            self._disarm()
            return

        if action in ("turn_left", "turn_right"):
            degrees = abs(float(waypoint.get("turn_degrees", 90.0)))
            if action == "turn_right":
                degrees = -degrees
            self.turn_start_heading = self.heading.heading_deg
            self.turn_target = wrap_degrees(self.heading.heading_deg + degrees)
            self._advance_route()
            self.state = "TURN"
            self.segment_started = time.monotonic()
            return

        # Straight/checkpoint: use the current direction as the new reference.
        self.target_heading = self.heading.heading_deg
        self._advance_route()
        if self.route_index >= len(self.route):
            self._disarm()
        else:
            self.segment_started = time.monotonic()

    def _advance_route(self) -> None:
        self.route_index += 1

    def _draw_debug(self, image: np.ndarray, markers: list[dict[str, Any]]) -> None:
        for marker in markers:
            points = marker["corners"].astype(int)
            cv2.polylines(image, [points], True, (0, 255, 0), 2)
            x, y = points[0]
            cv2.putText(
                image,
                f"ID {marker['id']} A={marker['area_ratio']:.3f}",
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )

        expected_id = self.route[self.route_index]["id"] if self.route_index < len(self.route) else "-"
        lines = [
            f"State: {self.state}",
            f"Keys: {self.start_key}=start {self.restart_key}=restart {self.speed_down_key}/{self.speed_up_key}=speed {self.gyro_axis_key}=axis {self.quit_key}=quit",
            f"Speed scale: {self.speed_scale:.2f}",
            f"Expected marker: {expected_id}",
            f"Gyro heading: {self.heading.heading_deg:.1f}",
            f"Target heading: {self.target_heading:.1f}",
            f"Gyro axis: {self.heading.axis} samples: {self.gyro_sample_count}",
        ]
        if self.last_gyro_values is not None:
            lines.append(
                "Gyro raw: "
                + " ".join(f"{value:+.3f}" for value in self.last_gyro_values[:3])
            )
        for index, text in enumerate(lines):
            cv2.putText(
                image,
                text,
                (10, 24 + index * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--route", default="route.json")
    parser.add_argument("--gpio", action="store_true", help="Enable actual GPIO motor output")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Arm navigation immediately; useful for headless/background runs",
    )
    args = parser.parse_args()

    config = load_json(args.config)
    route_data = load_json(args.route)
    navigator = Navigator(config, route_data["route"], args.gpio, args.autostart)

    def stop_handler(_signum: int, _frame: Any) -> None:
        navigator.request_stop()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    navigator.run(headless=args.headless)


if __name__ == "__main__":
    main()
