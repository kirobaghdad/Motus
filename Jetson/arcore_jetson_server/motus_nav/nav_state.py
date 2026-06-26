from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .math_utils import distance, wrap_angle
from .planner import RoutePlanner
from .settings import CarSettings


@dataclass
class Pose2D:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


@dataclass
class NavState:
    lock: threading.RLock = field(default_factory=threading.RLock)
    init_pose: Pose2D | None = None
    local_pose: Pose2D | None = None
    map_pose: Pose2D | None = None
    previous_local: Pose2D | None = None
    pose_time: float = 0.0
    local_distance_m: float = 0.0
    last_pose_step_m: float = 0.0
    pose_speed_mps: float = 0.0
    tracking: bool = False
    tracking_reason: str = "No phone pose received"
    phone_connected: bool = False
    origin_id: int | None = None
    nav_mode: str = "IDLE"
    nav_message: str = "Set the initial pose and choose a destination"
    goal_id: str | None = None
    path: list[tuple[float, float]] = field(default_factory=list)
    path_index: int = 0
    last_steering: float = 0.0
    last_pwm: float = 0.0
    control_debug: dict[str, Any] = field(default_factory=dict)

    def set_initial_pose(self, x: float, y: float, yaw: float) -> None:
        with self.lock:
            self.init_pose = Pose2D(x, y, wrap_angle(yaw))
            self.path = []
            self.path_index = 0
            self.nav_mode = "READY"
            self.nav_message = "Initial map pose set"
            self._update_map_pose_locked()

    def update_phone_pose(
        self,
        local_x: float,
        local_y: float,
        local_yaw: float,
        origin_id: int,
        tracking: bool,
        reason: str,
        settings: CarSettings,
    ) -> None:
        with self.lock:
            next_pose = Pose2D(local_x, local_y, wrap_angle(local_yaw))

            if self.origin_id != origin_id:
                self.origin_id = origin_id
                self.previous_local = None
                self.local_distance_m = 0.0
                self.last_pose_step_m = 0.0
                self.pose_speed_mps = 0.0

            step = 0.0
            if tracking and self.previous_local is not None:
                step = distance(
                    (next_pose.x, next_pose.y),
                    (self.previous_local.x, self.previous_local.y),
                )
                if step > settings.max_pose_step_m:
                    self.tracking = False
                    self.tracking_reason = f"Rejected ARCore jump of {step:.2f} m"
                    self.pose_time = time.monotonic()
                    return

            if tracking:
                now = time.monotonic()
                dt = 0.0 if self.pose_time == 0 else now - self.pose_time
                self.local_distance_m += step
                self.last_pose_step_m = step
                self.pose_speed_mps = 0.0 if dt <= 0 else step / dt
                self.local_pose = next_pose
                self.previous_local = next_pose
                self._update_map_pose_locked()

            self.pose_time = time.monotonic()
            self.tracking = tracking
            self.tracking_reason = reason if reason else ("TRACKING" if tracking else "Not tracking")

    def _update_map_pose_locked(self) -> None:
        if self.init_pose is None or self.local_pose is None:
            return

        start = self.init_pose
        local = self.local_pose
        c = math.cos(start.yaw)
        s = math.sin(start.yaw)

        self.map_pose = Pose2D(
            x=start.x + c * local.x - s * local.y,
            y=start.y + s * local.x + c * local.y,
            yaw=wrap_angle(start.yaw + local.yaw),
        )

    def plan_goal(self, goal_id: str, planner: RoutePlanner) -> list[tuple[float, float]]:
        with self.lock:
            if self.map_pose is None:
                raise ValueError("Set the initial pose and receive ARCore tracking first")
            self.goal_id = goal_id
            self.path = planner.plan((self.map_pose.x, self.map_pose.y), goal_id)
            self.path_index = 0
            self.nav_mode = "PLANNED"
            self.nav_message = f"Route planned to {planner.nodes[goal_id].name}"
            return list(self.path)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            pose_age = None if self.pose_time == 0 else time.monotonic() - self.pose_time
            return {
                "phone_connected": self.phone_connected,
                "origin_id": self.origin_id,
                "tracking": self.tracking,
                "tracking_reason": self.tracking_reason,
                "pose_age_s": None if pose_age is None else round(pose_age, 3),
                "pose_odometry": {
                    "local_distance_m": round(self.local_distance_m, 3),
                    "last_step_m": round(self.last_pose_step_m, 3),
                    "pose_speed_mps": round(self.pose_speed_mps, 3),
                },
                "local_pose": _pose_dict(self.local_pose),
                "map_pose": _pose_dict(self.map_pose),
                "init_pose": _pose_dict(self.init_pose),
                "mode": self.nav_mode,
                "message": self.nav_message,
                "goal_id": self.goal_id,
                "path": [[round(x, 3), round(y, 3)] for x, y in self.path],
                "path_index": self.path_index,
                "steering": round(self.last_steering, 3),
                "speed_pwm": round(self.last_pwm, 2),
                "control_debug": self.control_debug,
            }


def _pose_dict(pose: Pose2D | None) -> dict[str, float] | None:
    if pose is None:
        return None
    return {
        "x": round(pose.x, 4),
        "y": round(pose.y, 4),
        "yaw": round(pose.yaw, 5),
        "yaw_deg": round(math.degrees(pose.yaw), 2),
    }
