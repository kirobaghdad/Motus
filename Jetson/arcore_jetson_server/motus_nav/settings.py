from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def load_json(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@dataclass
class CarSettings:
    hardware_enabled: bool
    motor_pwm_pin: int
    motor_dir_pin: int
    servo_channel: int
    servo_address: int
    servo_center_deg: float
    servo_range_deg: float
    servo_sign: float
    motor_sign: float
    motor_ramp_step: float
    motor_ramp_interval: float
    max_manual_pwm: float
    wheelbase_m: float
    max_steer_deg: float
    auto_steering_sign: float
    lookahead_m: float
    turn_lookahead_m: float
    corner_anticipation_m: float
    power_mode: str
    power_profiles: dict[str, dict[str, float]]
    normal_pwm: float
    turn_pwm: float
    goal_tolerance_m: float
    path_tolerance_m: float
    pose_timeout_s: float
    max_pose_step_m: float
    control_hz: float

    @classmethod
    def from_file(cls) -> "CarSettings":
        data = load_json("car.json")
        hw = data["hardware"]
        servo = data["servo"]
        motor = data["motor"]
        control = data["control"]
        power_mode = str(control.get("power_mode", "direct_ac"))
        power_profiles = {
            name: {
                "normal_pwm": float(profile["normal_pwm"]),
                "turn_pwm": float(profile["turn_pwm"]),
            }
            for name, profile in control.get("power_profiles", {}).items()
        }
        if power_mode in power_profiles:
            normal_pwm = power_profiles[power_mode]["normal_pwm"]
            turn_pwm = power_profiles[power_mode]["turn_pwm"]
        else:
            normal_pwm = float(control["normal_pwm"])
            turn_pwm = float(control["turn_pwm"])

        return cls(
            hardware_enabled=bool(hw.get("enabled", True)) and os.environ.get("MOTUS_SIM") != "1",
            motor_pwm_pin=int(hw["motor_pwm_pin"]),
            motor_dir_pin=int(hw["motor_dir_pin"]),
            servo_channel=int(hw["servo_channel"]),
            servo_address=int(str(hw.get("servo_address", "0x40")), 0),
            servo_center_deg=float(servo["center_deg"]),
            servo_range_deg=float(servo["range_deg"]),
            servo_sign=float(servo.get("sign", 1.0)),
            motor_sign=float(motor.get("sign", 1.0)),
            motor_ramp_step=float(motor.get("ramp_step", 4.0)),
            motor_ramp_interval=float(motor.get("ramp_interval", 0.05)),
            max_manual_pwm=float(motor.get("max_manual_pwm", 99.0)),
            wheelbase_m=float(control["wheelbase_m"]),
            max_steer_deg=float(control["max_steer_deg"]),
            auto_steering_sign=float(control.get("auto_steering_sign", -1.0)),
            lookahead_m=float(control["lookahead_m"]),
            turn_lookahead_m=float(control.get("turn_lookahead_m", control["lookahead_m"])),
            corner_anticipation_m=float(control.get("corner_anticipation_m", 0.0)),
            power_mode=power_mode,
            power_profiles=power_profiles,
            normal_pwm=normal_pwm,
            turn_pwm=turn_pwm,
            goal_tolerance_m=float(control["goal_tolerance_m"]),
            path_tolerance_m=float(control["path_tolerance_m"]),
            pose_timeout_s=float(control["pose_timeout_s"]),
            max_pose_step_m=float(control["max_pose_step_m"]),
            control_hz=float(control.get("control_hz", 20.0)),
        )
