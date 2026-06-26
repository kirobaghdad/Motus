from __future__ import annotations

import atexit
import base64
import binascii
import json
import math
import time

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api_models import (
    GoalRequest,
    InitialPoseRequest,
    ManualRequest,
    MapEditorSaveRequest,
    PowerModeRequest,
    ServoConfigRequest,
)
from .controller import NavController
from .hardware import build_hardware
from .nav_state import NavState
from .planner import RoutePlanner
from .settings import BASE_DIR, CarSettings, load_json


settings = CarSettings.from_file()
planner = RoutePlanner()
state = NavState()
hardware = build_hardware(settings)
controller = NavController(settings, state, hardware)
map_data = load_json("map.json")
static_dir = BASE_DIR / "static"
initial_pose_path = BASE_DIR / "config" / "initial_pose.json"
car_config_path = BASE_DIR / "config" / "car.json"
map_config_path = BASE_DIR / "config" / "map.json"
graph_config_path = BASE_DIR / "config" / "graph.json"
map_image_path = static_dir / "map.png"
legacy_map_image_path = BASE_DIR / "config" / "map.png"

app = FastAPI(title="Motus ARCore Navigation", version="1.0")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.middleware("http")
async def no_cache_static_and_pages(request, call_next):
    response = await call_next(request)
    if (
        request.url.path in {"/", "/map-editor"}
        or request.url.path.startswith("/static/")
        or request.url.path.startswith("/api/config")
        or request.url.path.startswith("/api/map-editor")
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


def load_initial_pose() -> None:
    if not initial_pose_path.exists():
        return

    try:
        with initial_pose_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        state.set_initial_pose(
            x=float(data["x"]),
            y=float(data["y"]),
            yaw=float(data["yaw"]),
        )
        state.nav_message = "Initial map pose loaded"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Could not load initial pose from {initial_pose_path}: {error}")


def save_initial_pose(x: float, y: float, yaw: float) -> None:
    data = {"x": x, "y": y, "yaw": yaw}
    tmp_path = initial_pose_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    tmp_path.replace(initial_pose_path)


def save_car_settings() -> None:
    data = load_json("car.json")
    data["servo"]["center_deg"] = settings.servo_center_deg
    data["servo"]["range_deg"] = settings.servo_range_deg
    data["control"]["power_mode"] = settings.power_mode
    data["control"]["normal_pwm"] = settings.normal_pwm
    data["control"]["turn_pwm"] = settings.turn_pwm
    tmp_path = car_config_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    tmp_path.replace(car_config_path)


def power_config() -> dict:
    return {
        "mode": settings.power_mode,
        "normal_pwm": settings.normal_pwm,
        "turn_pwm": settings.turn_pwm,
        "profiles": settings.power_profiles,
    }


def map_image_version() -> int:
    version = 0
    for path in (map_image_path, legacy_map_image_path, map_config_path, graph_config_path):
        try:
            version = max(version, int(path.stat().st_mtime))
        except OSError:
            pass
    return version or int(time.time())


def write_json_atomic(path, data: dict) -> None:
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    tmp_path.replace(path)


def raw_graph_data() -> dict:
    return load_json("graph.json")


def reload_navigation_map() -> None:
    global map_data, planner
    controller.stop("Map reloaded; choose a destination")
    map_data = load_json("map.json")
    planner = RoutePlanner()
    with state.lock:
        state.path = []
        state.path_index = 0
        state.goal_id = None
        state.nav_mode = "READY" if state.init_pose else "IDLE"
        state.nav_message = "Map reloaded; choose a destination"


def image_payload_to_png_bytes(image_data: str) -> bytes:
    if "," in image_data:
        header, payload = image_data.split(",", 1)
        if "image/" not in header:
            raise ValueError("Image payload must be an image data URL")
    else:
        payload = image_data

    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Invalid base64 image payload") from error


load_initial_pose()


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/map-editor")
def map_editor():
    return FileResponse(static_dir / "map_editor.html")


@app.get("/api/config")
def get_config():
    return {
        "map": map_data,
        "graph": planner.public_data(),
        "image_version": map_image_version(),
        "control": {
            "lookahead_m": settings.lookahead_m,
            "turn_lookahead_m": settings.turn_lookahead_m,
            "corner_anticipation_m": settings.corner_anticipation_m,
            "goal_tolerance_m": settings.goal_tolerance_m,
            "normal_pwm": settings.normal_pwm,
            "turn_pwm": settings.turn_pwm,
            "max_manual_pwm": settings.max_manual_pwm,
            "power": power_config(),
        },
    }


@app.get("/api/map-editor")
def get_map_editor_data():
    return {
        "map": map_data,
        "graph": raw_graph_data(),
        "image_version": map_image_version(),
    }


@app.post("/api/map-editor/save")
def save_map_editor_data(data: MapEditorSaveRequest):
    node_ids = [node.id.strip() for node in data.graph.nodes]
    if any(not node_id for node_id in node_ids):
        raise HTTPException(status_code=400, detail="Every node needs an id")
    if len(set(node_ids)) != len(node_ids):
        raise HTTPException(status_code=400, detail="Node ids must be unique")

    valid_ids = set(node_ids)
    for edge in data.graph.edges:
        if edge.a not in valid_ids or edge.b not in valid_ids:
            raise HTTPException(status_code=400, detail=f"Edge {edge.a} -> {edge.b} references a missing node")
        if edge.a == edge.b:
            raise HTTPException(status_code=400, detail="Edges must connect two different nodes")

    map_payload = data.map.model_dump()
    map_payload["image"] = "/static/map.png"
    graph_payload = {
        "nodes": [
            {key: value for key, value in node.model_dump().items() if value is not None}
            for node in data.graph.nodes
        ],
        "edges": [
            {key: value for key, value in edge.model_dump().items() if value is not None and value is not False}
            for edge in data.graph.edges
        ],
    }

    if data.image_data:
        try:
            image_bytes = image_payload_to_png_bytes(data.image_data)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        tmp_image_path = map_image_path.with_suffix(".tmp")
        with tmp_image_path.open("wb") as file:
            file.write(image_bytes)
        tmp_image_path.replace(map_image_path)
        tmp_legacy_image_path = legacy_map_image_path.with_suffix(".tmp")
        with tmp_legacy_image_path.open("wb") as file:
            file.write(image_bytes)
        tmp_legacy_image_path.replace(legacy_map_image_path)

    write_json_atomic(map_config_path, map_payload)
    write_json_atomic(graph_config_path, graph_payload)
    reload_navigation_map()

    return {
        "ok": True,
        "map": map_data,
        "graph": raw_graph_data(),
        "image_version": map_image_version(),
        "message": "Map saved and navigation reloaded",
    }


@app.get("/api/status")
def get_status():
    snapshot = state.snapshot()
    snapshot["hardware"] = hardware.status().__dict__
    snapshot["servo"] = hardware.steering_config()
    snapshot["power"] = power_config()
    return snapshot


@app.get("/api/power")
def get_power_mode():
    return power_config()


@app.post("/api/power")
def set_power_mode(data: PowerModeRequest):
    mode = data.mode.strip().lower()
    if mode not in settings.power_profiles:
        valid = ", ".join(sorted(settings.power_profiles))
        raise HTTPException(status_code=400, detail=f"Unknown power mode. Valid modes: {valid}")

    profile = settings.power_profiles[mode]
    settings.power_mode = mode
    settings.normal_pwm = profile["normal_pwm"]
    settings.turn_pwm = profile["turn_pwm"]
    save_car_settings()
    return power_config()


@app.get("/api/servo")
def get_servo_config():
    return hardware.steering_config()


@app.post("/api/servo")
def set_servo_config(data: ServoConfigRequest):
    config = hardware.set_steering_config(data.center_deg, data.range_deg)
    settings.servo_center_deg = config["center_deg"]
    settings.servo_range_deg = config["range_deg"]
    save_car_settings()
    return config


@app.post("/api/init")
def set_initial_pose(data: InitialPoseRequest):
    yaw = math.radians(data.yaw_deg)
    state.set_initial_pose(data.x, data.y, yaw)
    save_initial_pose(data.x, data.y, yaw)
    return {"ok": True, "message": "Initial pose set"}


@app.post("/api/goal")
def set_goal(data: GoalRequest):
    try:
        path = state.plan_goal(data.goal_id, planner)
        return {"ok": True, "path": path}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/start")
def start_navigation():
    try:
        controller.start()
        return {"ok": True, "message": "Navigation started"}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/stop")
def stop_navigation():
    controller.stop()
    return {"ok": True, "message": "Vehicle stopped"}


@app.post("/api/manual")
def manual_control(data: ManualRequest):
    try:
        controller.manual(data.speed_pwm, data.steering)
        return {"ok": True}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.websocket("/ws/pose")
async def pose_socket(socket: WebSocket):
    await socket.accept()
    with state.lock:
        state.phone_connected = True
        state.tracking_reason = "Phone connected; waiting for ARCore tracking"

    packet_count = 0
    try:
        await socket.send_json({"type": "hello", "message": "Motus Jetson pose server"})
        while True:
            data = await socket.receive_json()
            if data.get("type") != "pose":
                continue

            state.update_phone_pose(
                local_x=float(data.get("local_x", 0.0)),
                local_y=float(data.get("local_y", 0.0)),
                local_yaw=float(data.get("local_yaw", 0.0)),
                origin_id=int(data.get("origin_id", 0)),
                tracking=bool(data.get("tracking", False)),
                reason=str(data.get("reason", "")),
                settings=settings,
            )

            packet_count += 1
            if packet_count % 20 == 0:
                await socket.send_json({"type": "ack", "seq": data.get("seq")})
    except WebSocketDisconnect:
        pass
    except Exception as error:
        print(f"Pose socket error: {error}")
    finally:
        with state.lock:
            state.phone_connected = False
            state.tracking = False
            state.tracking_reason = "Phone disconnected"
        controller.stop("Safety stop: phone disconnected")


def cleanup() -> None:
    controller.cleanup()


atexit.register(cleanup)
