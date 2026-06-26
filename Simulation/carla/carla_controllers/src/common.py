from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """return the carla_controllers folder."""
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path, root: Path | None = None) -> Path:
    """resolve config paths relative to the controller project."""
    path = Path(value)
    if path.is_absolute():
        return path
    return (root or project_root()) / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    """load a yaml file and make sure it contains a mapping."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    """write a small json artifact, creating its folder if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def create_run_dir(base_dir: str | Path, prefix: str) -> Path:
    """create a new timestamped run folder."""
    base_dir = Path(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"{prefix}_{timestamp}"
    counter = 1
    # keep old runs intact if two runs start in the same second.
    while run_dir.exists():
        run_dir = base_dir / f"{prefix}_{timestamp}_{counter:02d}"
        counter += 1
    run_dir.mkdir(parents=True)
    return run_dir


def speed_kmh(velocity: Any) -> float:
    """convert a carla velocity vector from m/s to km/h."""
    magnitude = math.sqrt(
        velocity.x * velocity.x
        + velocity.y * velocity.y
        + velocity.z * velocity.z
    )
    return 3.6 * magnitude


def normalize_angle_degrees(angle: float) -> float:
    """normalize an angle to the -180..180 degree range."""
    # convert any heading difference to the shortest signed angle.
    return (angle + 180.0) % 360.0 - 180.0


def target_speed_at(profile: list[dict[str, float]], elapsed: float) -> float:
    """read the target speed from a time-based speed profile."""
    for stage in profile:
        if stage["start_seconds"] <= elapsed < stage["end_seconds"]:
            return float(stage["target_kmh"])
    if profile and math.isclose(elapsed, profile[-1]["end_seconds"]):
        return float(profile[-1]["target_kmh"])
    raise ValueError(f"No speed-profile stage covers t={elapsed:.3f}s")


def validate_pid_config(config: dict[str, Any]) -> None:
    """check the fields needed by the pid speed experiment."""
    required_sections = {"carla", "vehicle", "control", "acceptance", "outputs"}
    missing = sorted(required_sections - config.keys())
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(missing)}")

    carla_cfg = config["carla"]
    dt = float(carla_cfg["fixed_delta_seconds"])
    if dt <= 0:
        raise ValueError("fixed_delta_seconds must be positive")

    control = config["control"]
    duration = float(control["duration_seconds"])
    if duration <= 0:
        raise ValueError("duration_seconds must be positive")
    for name in ("max_throttle", "max_brake"):
        value = float(control[name])
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be in (0, 1]")

    pid = control["pid"]
    for name in ("kp", "ki", "kd", "integral_limit"):
        if float(pid[name]) < 0:
            raise ValueError(f"PID value {name} cannot be negative")
    smoothing = float(pid["derivative_smoothing"])
    if not 0.0 <= smoothing < 1.0:
        raise ValueError("derivative_smoothing must be in [0, 1)")

    profile = control["speed_profile"]
    if not profile:
        raise ValueError("speed_profile cannot be empty")

    expected_start = 0.0
    for index, stage in enumerate(profile):
        # the profile must cover the run without gaps or overlaps.
        start = float(stage["start_seconds"])
        end = float(stage["end_seconds"])
        target = float(stage["target_kmh"])
        if not math.isclose(start, expected_start, abs_tol=1e-9):
            raise ValueError(f"Speed-profile stage {index} is not contiguous")
        if end <= start:
            raise ValueError(f"Speed-profile stage {index} has an invalid duration")
        if target < 0:
            raise ValueError(f"Speed-profile stage {index} has a negative target")
        expected_start = end

    if not math.isclose(expected_start, duration, abs_tol=1e-9):
        raise ValueError("The speed profile must cover the full experiment duration")

    road = config["vehicle"]["straight_road"]
    if float(road["required_distance_m"]) <= 0 or float(road["step_m"]) <= 0:
        raise ValueError("Straight road distances must be positive")
