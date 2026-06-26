from __future__ import annotations

from typing import Any

from common import normalize_angle_degrees


class CarlaSession:
    """small context manager for a synchronous carla run."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float,
        fixed_delta_seconds: float,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.fixed_delta_seconds = fixed_delta_seconds
        self.client: Any = None
        self.world: Any = None
        self.original_settings: Any = None
        self.actors: list[Any] = []
        self.sensors: list[Any] = []
        self._active = False

    def __enter__(self) -> "CarlaSession":
        """connect to carla and switch the world into fixed-step mode."""
        import carla

        # keep the original settings so cleanup can restore the simulator.
        self.carla = carla
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(self.timeout_seconds)
        self.world = self.client.get_world()
        self.original_settings = self.world.get_settings()
        self._active = True

        try:
            # synchronous mode makes every control step repeatable.
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = self.fixed_delta_seconds
            self.world.apply_settings(settings)
            self.world.tick()
        except Exception:
            self.close()
            raise
        return self

    def check_map(self, expected_map: str) -> str:
        """make sure the loaded town matches the config."""
        map_name = self.world.get_map().name
        short_name = map_name.rsplit("/", 1)[-1]
        if expected_map and short_name != expected_map:
            raise RuntimeError(
                f"Expected map {expected_map}, but CARLA is running {short_name}. "
                "Load the expected town before running the experiment."
            )
        return map_name

    def register_actor(self, actor: Any, sensor: bool = False) -> Any:
        """remember an actor so it can be cleaned up later."""
        # every spawned actor is registered so close() can remove it later.
        self.actors.append(actor)
        if sensor:
            self.sensors.append(actor)
        return actor

    def spawn_vehicle(self, blueprint_filter: str, transform: Any) -> Any:
        """spawn the ego vehicle from the first matching blueprint."""
        blueprints = sorted(
            self.world.get_blueprint_library().filter(blueprint_filter),
            key=lambda blueprint: blueprint.id,
        )
        if not blueprints:
            raise RuntimeError(f"No vehicle blueprint matches {blueprint_filter}")

        blueprint = blueprints[0]
        if blueprint.has_attribute("role_name"):
            blueprint.set_attribute("role_name", "ego")
        vehicle = self.world.try_spawn_actor(blueprint, transform)
        if vehicle is None:
            raise RuntimeError("The selected ego spawn point is occupied")
        return self.register_actor(vehicle)

    def tick(self) -> int:
        """advance the synchronous world by one frame."""
        return self.world.tick()

    def update_spectator(self, vehicle: Any) -> None:
        """place the spectator camera behind the ego vehicle."""
        transform = vehicle.get_transform()
        location = (
            transform.location
            + self.carla.Location(z=3.0)
            - transform.get_forward_vector() * 6.0
        )
        rotation = self.carla.Rotation(
            pitch=-15.0,
            yaw=transform.rotation.yaw,
        )
        self.world.get_spectator().set_transform(
            self.carla.Transform(location, rotation)
        )

    def close(self) -> None:
        """destroy registered actors and restore the original world settings."""
        if not self._active:
            return

        # sensors should stop callbacks before their actors are destroyed.
        for sensor in self.sensors:
            try:
                if sensor.is_alive:
                    sensor.stop()
            except RuntimeError:
                pass

        alive_actors = []
        for actor in self.actors:
            try:
                if actor.is_alive:
                    alive_actors.append(actor)
            except RuntimeError:
                pass

        batch_failed = False
        if alive_actors:
            commands = [
                self.carla.command.DestroyActor(actor.id) for actor in alive_actors
            ]
            try:
                # batch destroy is faster, but the fallback below is safer.
                self.client.apply_batch_sync(commands, True)
            except Exception:
                batch_failed = True

        try:
            self.world.apply_settings(self.original_settings)
        finally:
            if batch_failed:
                for actor in reversed(alive_actors):
                    try:
                        if actor.is_alive:
                            actor.destroy()
                    except RuntimeError:
                        pass
            self.actors.clear()
            self.sensors.clear()
            self._active = False

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self.close()
        return False


def select_straight_spawn(
    world_map: Any,
    spawn_points: list[Any],
    required_distance_m: float,
    step_m: float,
    max_heading_change_deg: float,
    allow_junctions: bool,
    height_offset_m: float,
    spawn_index: int | None = None,
) -> tuple[Any, int]:
    """choose a spawn point with enough straight road ahead."""
    import carla

    if spawn_index is not None:
        if not 0 <= spawn_index < len(spawn_points):
            raise ValueError(f"spawn_index must be between 0 and {len(spawn_points) - 1}")
        transform = _copy_spawn(spawn_points[spawn_index], height_offset_m)
        return transform, spawn_index

    for index, spawn in enumerate(spawn_points):
        waypoint = world_map.get_waypoint(
            spawn.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
        if waypoint is None or waypoint.is_junction and not allow_junctions:
            continue

        start_yaw = waypoint.transform.rotation.yaw
        current = waypoint
        distance = 0.0
        valid = True

        while distance < required_distance_m:
            candidates = current.next(step_m)
            if not candidates:
                valid = False
                break

            # at junctions, keep the branch with the smallest heading change.
            candidate = min(
                candidates,
                key=lambda item: abs(
                    normalize_angle_degrees(
                        item.transform.rotation.yaw - current.transform.rotation.yaw
                    )
                ),
            )
            heading_change = abs(
                normalize_angle_degrees(candidate.transform.rotation.yaw - start_yaw)
            )
            if candidate.is_junction and not allow_junctions:
                valid = False
                break
            if heading_change > max_heading_change_deg:
                valid = False
                break

            distance += current.transform.location.distance(
                candidate.transform.location
            )
            current = candidate

        if valid and distance >= required_distance_m:
            return _copy_spawn(spawn, height_offset_m), index

    raise RuntimeError(
        "No spawn point has the configured straight road distance. "
    )


def _copy_spawn(spawn: Any, height_offset_m: float) -> Any:
    """copy a spawn transform and lift it slightly above the road."""
    import carla

    location = carla.Location(
        x=spawn.location.x,
        y=spawn.location.y,
        z=spawn.location.z + height_offset_m,
    )
    rotation = carla.Rotation(
        pitch=spawn.rotation.pitch,
        yaw=spawn.rotation.yaw,
        roll=spawn.rotation.roll,
    )
    return carla.Transform(location, rotation)
