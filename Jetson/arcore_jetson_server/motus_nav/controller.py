from __future__ import annotations

import math
import threading
import time

from .math_utils import clamp, distance
from .nav_state import NavState
from .settings import CarSettings


class NavController:
    def __init__(self, settings: CarSettings, state: NavState, hardware) -> None:
        self.settings = settings
        self.state = state
        self.hardware = hardware
        self.running = True
        self.manual_block_until = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def start(self) -> None:
        with self.state.lock:
            if not self.state.path:
                raise ValueError("Plan a route before starting")
            if self.state.map_pose is None or self.state.init_pose is None:
                raise ValueError("Initial pose is not ready")
            if not self.state.tracking:
                raise ValueError("ARCore is not tracking")
            self.state.nav_mode = "NAVIGATING"
            self.state.nav_message = "Following planned path"

    def stop(self, message: str = "Stopped by user") -> None:
        self.manual_block_until = time.monotonic() + 1.0
        self.hardware.stop(center=True)
        with self.state.lock:
            self.state.nav_mode = "STOPPED"
            self.state.nav_message = message
            self.state.last_pwm = 0.0
            self.state.last_steering = 0.0

    def manual(self, speed_pwm: float, steering: float) -> None:
        if time.monotonic() < self.manual_block_until:
            self.hardware.stop(center=True)
            with self.state.lock:
                self.state.nav_mode = "STOPPED"
                self.state.nav_message = "Manual command ignored after emergency stop"
                self.state.last_pwm = 0.0
                self.state.last_steering = 0.0
            return

        speed_pwm = clamp(speed_pwm, -self.settings.max_manual_pwm, self.settings.max_manual_pwm)
        steering = clamp(steering, -1.0, 1.0)

        with self.state.lock:
            if self.state.nav_mode == "NAVIGATING":
                raise ValueError("Stop autonomous navigation before manual control")
            self.state.nav_mode = "MANUAL"
            self.state.nav_message = "Manual hardware test"
            self.state.last_pwm = speed_pwm
            self.state.last_steering = steering
        self.hardware.command(speed_pwm, steering)

    def _loop(self) -> None:
        interval = 1.0 / self.settings.control_hz
        while self.running:
            started = time.monotonic()
            self._control_step()
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval - elapsed))

    def _control_step(self) -> None:
        with self.state.lock:
            if self.state.nav_mode != "NAVIGATING":
                return

            pose = self.state.map_pose
            path = list(self.state.path)
            pose_age = time.monotonic() - self.state.pose_time
            tracking = self.state.tracking

        if not tracking:
            self._localization_hold("Localization hold: ARCore tracking lost")
            return
        if pose_age > self.settings.pose_timeout_s:
            self._localization_hold(f"Localization hold: pose is {pose_age:.2f} s old")
            return
        if pose is None or not path:
            self.stop("Safety stop: pose or path missing")
            return

        goal = path[-1]
        goal_dist = distance((pose.x, pose.y), goal)
        if goal_dist <= self.settings.goal_tolerance_m:
            self.hardware.stop(center=True)
            with self.state.lock:
                self.state.nav_mode = "GOAL_REACHED"
                self.state.nav_message = "Destination reached"
                self.state.last_pwm = 0.0
                self.state.last_steering = 0.0
            return

        target, closest_index, path_error, lookahead, corner_distance = self._find_target(
            pose.x,
            pose.y,
            path,
        )
        if path_error > self.settings.path_tolerance_m:
            hard_tolerance = max(1.5, self.settings.path_tolerance_m * 2.0)
            if path_error > hard_tolerance:
                self.stop(f"Safety stop: {path_error:.2f} m away from path")
                return

        heading_error = math.atan2(target[1] - pose.y, target[0] - pose.x) - pose.yaw
        while heading_error > math.pi:
            heading_error -= 2.0 * math.pi
        while heading_error < -math.pi:
            heading_error += 2.0 * math.pi

        raw_steering = self._pure_pursuit(pose.x, pose.y, pose.yaw, target)
        steering = clamp(raw_steering * self.settings.auto_steering_sign, -1.0, 1.0)
        speed_pwm = self._select_speed(steering, goal_dist, corner_distance)
        recovering_path = path_error > self.settings.path_tolerance_m
        if recovering_path:
            speed_pwm = min(speed_pwm, self.settings.turn_pwm)
        self.hardware.command(speed_pwm, steering)

        with self.state.lock:
            self.state.path_index = closest_index
            self.state.last_steering = steering
            self.state.last_pwm = speed_pwm
            self.state.control_debug = {
                "target_x": round(target[0], 3),
                "target_y": round(target[1], 3),
                "path_error_m": round(path_error, 3),
                "heading_error_deg": round(math.degrees(heading_error), 1),
                "lookahead_m": round(lookahead, 3),
                "corner_distance_m": None if corner_distance is None else round(corner_distance, 3),
                "raw_steering": round(raw_steering, 3),
                "auto_steering_sign": round(self.settings.auto_steering_sign, 3),
                "commanded_steering": round(steering, 3),
                "closest_index": closest_index,
            }
            if recovering_path:
                self.state.nav_message = f"Recovering path; error {path_error:.2f} m"
            else:
                self.state.nav_message = f"Driving; goal distance {goal_dist:.2f} m"

    def _find_target(
        self,
        x: float,
        y: float,
        path: list[tuple[float, float]],
    ) -> tuple[tuple[float, float], int, float, float, float | None]:
        with self.state.lock:
            start_index = max(0, self.state.path_index - 5)

        search_end = self._forward_search_end(
            path,
            start_index,
            max(2.0, self.settings.corner_anticipation_m + self.settings.turn_lookahead_m + 0.5),
        )
        search = range(start_index, search_end)
        closest_index = min(search, key=lambda i: distance((x, y), path[i]))
        path_error = distance((x, y), path[closest_index])
        corner_distance = self._upcoming_corner_distance(path, closest_index)
        lookahead = self.settings.lookahead_m

        if (
            corner_distance is not None
            and corner_distance <= self.settings.corner_anticipation_m
        ):
            lookahead = max(lookahead, self.settings.turn_lookahead_m)

        target = path[-1]
        for point in path[closest_index:]:
            if distance((x, y), point) >= lookahead:
                target = point
                break

        return target, closest_index, path_error, lookahead, corner_distance

    @staticmethod
    def _forward_search_end(
        path: list[tuple[float, float]],
        start_index: int,
        max_distance: float,
    ) -> int:
        traveled = 0.0
        for index in range(start_index + 1, len(path)):
            traveled += distance(path[index - 1], path[index])
            if traveled >= max_distance:
                return index + 1
        return len(path)

    @staticmethod
    def _upcoming_corner_distance(
        path: list[tuple[float, float]],
        closest_index: int,
    ) -> float | None:
        if len(path) < 3:
            return None

        traveled = 0.0
        start = max(1, closest_index)
        for index in range(start, len(path) - 1):
            if index > closest_index:
                traveled += distance(path[index - 1], path[index])

            prev_dx = path[index][0] - path[index - 1][0]
            prev_dy = path[index][1] - path[index - 1][1]
            next_dx = path[index + 1][0] - path[index][0]
            next_dy = path[index + 1][1] - path[index][1]

            if abs(prev_dx) < 1e-6 and abs(prev_dy) < 1e-6:
                continue
            if abs(next_dx) < 1e-6 and abs(next_dy) < 1e-6:
                continue

            prev_angle = math.atan2(prev_dy, prev_dx)
            next_angle = math.atan2(next_dy, next_dx)
            turn_angle = next_angle - prev_angle
            while turn_angle > math.pi:
                turn_angle -= 2.0 * math.pi
            while turn_angle < -math.pi:
                turn_angle += 2.0 * math.pi

            if abs(math.degrees(turn_angle)) >= 20.0:
                return traveled

        return None

    def _pure_pursuit(
        self,
        x: float,
        y: float,
        yaw: float,
        target: tuple[float, float],
    ) -> float:
        dx = target[0] - x
        dy = target[1] - y

        local_y = -math.sin(yaw) * dx + math.cos(yaw) * dy
        lookahead_sq = max(dx * dx + dy * dy, 0.01)
        curvature = 2.0 * local_y / lookahead_sq
        steer_rad = math.atan(self.settings.wheelbase_m * curvature)
        max_steer_rad = math.radians(self.settings.max_steer_deg)
        return clamp(steer_rad / max_steer_rad, -1.0, 1.0)

    def _select_speed(
        self,
        steering: float,
        goal_dist: float,
        corner_distance: float | None,
    ) -> float:
        turn_amount = min(abs(steering), 1.0)
        speed = self.settings.normal_pwm - (
            self.settings.normal_pwm - self.settings.turn_pwm
        ) * turn_amount

        if (
            corner_distance is not None
            and self.settings.corner_anticipation_m > 0.0
            and corner_distance <= self.settings.corner_anticipation_m
        ):
            corner_ratio = clamp(
                corner_distance / self.settings.corner_anticipation_m,
                0.0,
                1.0,
            )
            corner_speed = self.settings.turn_pwm + (
                self.settings.normal_pwm - self.settings.turn_pwm
            ) * corner_ratio
            speed = min(speed, corner_speed)

        if goal_dist < 0.45:
            speed = min(speed, self.settings.turn_pwm)
        return speed

    def _localization_hold(self, message: str) -> None:
        self.hardware.stop(center=True)
        with self.state.lock:
            self.state.nav_mode = "NAVIGATING"
            self.state.nav_message = message
            self.state.last_pwm = 0.0
            self.state.last_steering = 0.0

    def cleanup(self) -> None:
        self.running = False
        self.hardware.stop(center=True)
        self.hardware.cleanup()
