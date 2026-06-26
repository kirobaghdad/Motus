from pydantic import BaseModel, Field


class InitialPoseRequest(BaseModel):
    x: float
    y: float
    yaw_deg: float = 0.0


class GoalRequest(BaseModel):
    goal_id: str


class ManualRequest(BaseModel):
    speed_pwm: float = Field(ge=-100.0, le=100.0)
    steering: float = Field(ge=-1.0, le=1.0)


class ServoConfigRequest(BaseModel):
    center_deg: float = Field(ge=0.0, le=180.0)
    range_deg: float = Field(ge=0.0, le=80.0)


class PowerModeRequest(BaseModel):
    mode: str


class MapEditorMapRequest(BaseModel):
    image: str = "/static/map.png"
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    resolution_m_per_px: float = Field(gt=0.0)
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    name: str = "Motus Map"


class MapEditorNodeRequest(BaseModel):
    id: str
    name: str
    x: float
    y: float
    goal: bool = False
    speed_pwm: float | None = Field(default=None, ge=0.0, le=100.0)


class MapEditorEdgeRequest(BaseModel):
    a: str
    b: str
    cost: float | None = Field(default=None, gt=0.0)
    one_way: bool = False


class MapEditorGraphRequest(BaseModel):
    nodes: list[MapEditorNodeRequest]
    edges: list[MapEditorEdgeRequest]


class MapEditorSaveRequest(BaseModel):
    map: MapEditorMapRequest
    graph: MapEditorGraphRequest
    image_data: str | None = None
