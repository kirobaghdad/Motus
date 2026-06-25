from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

from carla_session import CarlaSession, select_straight_spawn
from common import (
    create_run_dir,
    load_yaml,
    project_root,
    resolve_path,
    speed_kmh,
    target_speed_at,
    validate_pid_config,
    write_json,
)
from pid_controller import LongitudinalPID, command_to_actuation


CSV_FIELDS = [
    "frame",
    "time_seconds",
    "target_speed_kmh",
    "speed_kmh",
    "speed_error_kmh",
    "pid_command",
    "throttle",
    "brake",
    "steer",
    "location_x",
    "location_y",
    "location_z",
]


def run_experiment(config_path: str | Path) -> dict[str, Any]:
    """run speed-control experiment and save artifacts."""
    config_path = Path(config_path).resolve()
    config = load_yaml(config_path)
    validate_pid_config(config)

    output_cfg = config["outputs"]
    run_dir = create_run_dir(
        resolve_path(output_cfg["runs_dir"]),
        output_cfg["run_prefix"],
    )
    # save the exact config before the simulator starts changing state.
    write_json(run_dir / "config_used.json", config)

    carla_cfg = config["carla"]
    vehicle_cfg = config["vehicle"]
    control_cfg = config["control"]
    pid_cfg = control_cfg["pid"]
    dt = float(carla_cfg["fixed_delta_seconds"])
    duration = float(control_cfg["duration_seconds"])

    controller = LongitudinalPID(
        kp=float(pid_cfg["kp"]),
        ki=float(pid_cfg["ki"]),
        kd=float(pid_cfg["kd"]),
        integral_limit=float(pid_cfg["integral_limit"]),
        derivative_smoothing=float(pid_cfg["derivative_smoothing"]),
    )

    telemetry: list[dict[str, float | int]] = []
    completed = False
    spawn_index: int | None = None
    failure: BaseException | None = None
    map_name: str | None = None

    session = CarlaSession(
        host=carla_cfg["host"],
        port=int(carla_cfg["port"]),
        timeout_seconds=float(carla_cfg["timeout_seconds"]),
        fixed_delta_seconds=dt,
    )

    try:
        with session:
            map_name = session.check_map(carla_cfg["expected_map"])
            world_map = session.world.get_map()
            spawn_points = world_map.get_spawn_points()
            road_cfg = vehicle_cfg["straight_road"]
            transform, spawn_index = select_straight_spawn(
                world_map=world_map,
                spawn_points=spawn_points,
                required_distance_m=float(road_cfg["required_distance_m"]),
                step_m=float(road_cfg["step_m"]),
                max_heading_change_deg=float(road_cfg["max_heading_change_deg"]),
                allow_junctions=bool(road_cfg["allow_junctions"]),
                height_offset_m=float(vehicle_cfg["spawn_height_offset_m"]),
                spawn_index=vehicle_cfg["spawn_index"],
            )
            vehicle = session.spawn_vehicle(
                vehicle_cfg["blueprint_filter"],
                transform,
            )
            vehicle.set_autopilot(False)
            session.tick()

            import carla

            profile = control_cfg["speed_profile"]
            previous_target: float | None = None
            total_steps = int(math.ceil(duration / dt))
            log_interval = max(1, int(round(1.0 / dt)))

            print(f"Map: {map_name}")
            print(f"Spawn index: {spawn_index}")
            print(f"Running PID speed profile for {duration:.1f} seconds")

            for step in range(total_steps):
                elapsed = step * dt
                target = target_speed_at(profile, elapsed)
                if previous_target is not None and target == 0 and previous_target != 0:
                    # clear accumulated error when the profile switches to stop.
                    controller.reset()

                current_speed = speed_kmh(vehicle.get_velocity())
                command = controller.update(target, current_speed, dt)
                throttle, brake = command_to_actuation(
                    command,
                    max_throttle=float(control_cfg["max_throttle"]),
                    max_brake=float(control_cfg["max_brake"]),
                )
                vehicle.apply_control(
                    carla.VehicleControl(
                        throttle=throttle,
                        brake=brake,
                        steer=0.0,
                    )
                )
                session.update_spectator(vehicle)
                # apply the command, then tick once and record the response.
                frame = session.tick()

                measured_speed = speed_kmh(vehicle.get_velocity())
                location = vehicle.get_location()
                telemetry.append(
                    {
                        "frame": frame,
                        "time_seconds": round(elapsed + dt, 3),
                        "target_speed_kmh": target,
                        "speed_kmh": measured_speed,
                        "speed_error_kmh": target - measured_speed,
                        "pid_command": command,
                        "throttle": throttle,
                        "brake": brake,
                        "steer": 0.0,
                        "location_x": location.x,
                        "location_y": location.y,
                        "location_z": location.z,
                    }
                )
                previous_target = target

                if (step + 1) % log_interval == 0:
                    print(
                        f"t={elapsed + dt:5.1f}s  target={target:4.1f} km/h  "
                        f"speed={measured_speed:4.1f} km/h"
                    )

            completed = True
    except BaseException as exc:
        failure = exc
    finally:
        # write partial outputs too; failed runs can still be useful.
        _write_telemetry(run_dir / "telemetry.csv", telemetry)
        summary = _build_summary(
            config=config,
            telemetry=telemetry,
            completed=completed,
            failure=failure,
            run_dir=run_dir,
            map_name=map_name,
            spawn_index=spawn_index,
        )
        write_json(run_dir / "summary.json", summary)

    if failure is not None:
        raise failure

    print(f"Run saved: {run_dir}")
    print(f"Acceptance passed: {summary['acceptance']['passed']}")
    return summary


def _write_telemetry(path: Path, rows: list[dict[str, float | int]]) -> None:
    """save per-frame telemetry as a csv file."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _build_summary(
    config: dict[str, Any],
    telemetry: list[dict[str, float | int]],
    completed: bool,
    failure: BaseException | None,
    run_dir: Path,
    map_name: str | None,
    spawn_index: int | None,
) -> dict[str, Any]:
    """calculate acceptance metrics from saved telemetry."""
    acceptance_cfg = config["acceptance"]
    ignore_seconds = float(acceptance_cfg["transition_ignore_seconds"])
    stage_metrics = []

    for stage in config["control"]["speed_profile"]:
        target = float(stage["target_kmh"])
        if target <= 0:
            continue
        # skip the first seconds after each target change.
        start = float(stage["start_seconds"]) + ignore_seconds
        end = float(stage["end_seconds"])
        samples = [
            float(row["speed_kmh"])
            for row in telemetry
            if start <= float(row["time_seconds"]) < end
        ]
        if samples:
            mae = sum(abs(target - speed) for speed in samples) / len(samples)
            overshoot = max(0.0, max(samples) - target)
        else:
            mae = None
            overshoot = None
        stage_metrics.append(
            {
                "target_kmh": target,
                "measurement_start_seconds": start,
                "measurement_end_seconds": end,
                "mae_kmh": mae,
                "overshoot_kmh": overshoot,
            }
        )

    final_speed = float(telemetry[-1]["speed_kmh"]) if telemetry else None
    simultaneous = any(
        float(row["throttle"]) > 0 and float(row["brake"]) > 0
        for row in telemetry
    )
    # every acceptance item must pass before the run is marked successful.
    metrics_available = bool(stage_metrics) and all(
        stage["mae_kmh"] is not None for stage in stage_metrics
    )
    stages_pass = metrics_available and all(
        stage["mae_kmh"] <= float(acceptance_cfg["max_mae_kmh"])
        and stage["overshoot_kmh"] <= float(acceptance_cfg["max_overshoot_kmh"])
        for stage in stage_metrics
    )
    final_pass = (
        final_speed is not None
        and final_speed <= float(acceptance_cfg["max_final_speed_kmh"])
    )
    passed = completed and failure is None and stages_pass and final_pass and not simultaneous

    return {
        "project_name": config["project_name"],
        "run_dir": str(run_dir),
        "map": map_name,
        "spawn_index": spawn_index,
        "completed": completed,
        "error": None if failure is None else f"{type(failure).__name__}: {failure}",
        "sample_count": len(telemetry),
        "stage_metrics": stage_metrics,
        "final_speed_kmh": final_speed,
        "simultaneous_throttle_brake": simultaneous,
        "acceptance": {
            "passed": passed,
            "max_mae_kmh": float(acceptance_cfg["max_mae_kmh"]),
            "max_overshoot_kmh": float(acceptance_cfg["max_overshoot_kmh"]),
            "max_final_speed_kmh": float(
                acceptance_cfg["max_final_speed_kmh"]
            ),
        },
    }


def main() -> None:
    """command-line entry point for the pid speed run."""
    parser = argparse.ArgumentParser(
        description="Run the CARLA longitudinal PID speed experiment."
    )
    parser.add_argument("--config", default="configs/pid_speed.yaml")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    config_path = resolve_path(args.config, project_root())
    config = load_yaml(config_path)
    validate_pid_config(config)
    if args.validate_only:
        print(f"Configuration valid: {config_path}")
        return

    run_experiment(config_path)


if __name__ == "__main__":
    main()
