"""HTTP request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import BoundingBox, EventStatus, EventType, JobStatus, Point, Severity, SourceType


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source: str = Field(default="local", max_length=500)
    location: str | None = Field(default=None, max_length=200)
    enabled: bool = True


class CameraResponse(CameraCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ZoneCreate(BaseModel):
    name: str = Field(default="Danger zone", min_length=1, max_length=120)
    polygon: list[Point] = Field(min_length=3)
    enabled: bool = True


class ZoneResponse(ZoneCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int | None
    created_at: datetime


class JobResponse(BaseModel):
    job_id: str
    source_type: SourceType | str
    status: JobStatus | str
    progress: float
    result_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ExperimentModelResponse(BaseModel):
    model_name: str
    weights: str
    dataset_name: str | None = None
    is_current: bool = False
    split: str
    imgsz: int
    evaluated_at: datetime | str | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    map50: float | None = None
    map50_95: float | None = None
    per_class: dict[str, dict[str, float]] = Field(default_factory=dict)


class DatasetSplitResponse(BaseModel):
    images: int
    labels: int
    boxes: int = 0
    errors: list[str] = Field(default_factory=list)


class ExperimentSummaryResponse(BaseModel):
    dataset_name: str
    dataset_version: str | None = None
    classes: list[str] = Field(default_factory=list)
    splits: dict[str, DatasetSplitResponse] = Field(default_factory=dict)
    models: list[ExperimentModelResponse] = Field(default_factory=list)
    notes: str | None = None


class DemoAssetResponse(BaseModel):
    """A local, curated asset that can be loaded from the demo workbench."""

    asset_id: str
    name: str
    source_type: SourceType | str
    url: str
    size: str | None = None
    duration_seconds: float | None = None
    sha256: str | None = None


class EventResponse(BaseModel):
    id: str
    event_type: EventType | str
    severity: Severity | str
    camera_id: str | None
    track_id: int | None
    timestamp: datetime
    evidence_path: str | None
    status: EventStatus | str
    zone_id: str | None
    message: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventUpdate(BaseModel):
    status: EventStatus


class DetectionResponse(BaseModel):
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None
    frame_index: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class FrameResponse(BaseModel):
    frame_index: int
    timestamp: datetime
    detections: list[DetectionResponse]
    events: list[EventResponse]


class InferenceResponse(BaseModel):
    job_id: str | None
    source_type: SourceType | str
    frames: list[FrameResponse]
    detections: list[DetectionResponse]
    events: list[EventResponse]
    result_path: str | None = None
    preview_path: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    total_events: int
    open_events: int
    acknowledged_events: int
    resolved_events: int
    events_by_type: dict[str, int]
    events_by_severity: dict[str, int]
    active_cameras: int
    jobs_today: int


class HealthResponse(BaseModel):
    status: str
    service: str
    detector_backend: str
    model_available: bool
    model_error: str | None = None
    model_path: str | None = None
    image_size: int | None = None
    batch_size: int | None = None
    half_requested: bool = False
    half_enabled: bool = False
    tensorrt_requested: bool = False
    tensorrt_active: bool = False
    video_decode_backend: str | None = None
    video_encode_backend: str | None = None
    video_queue_size: int | None = None
    queue_workers_requested: int = 1
    queue_workers_effective: int = 1
    ffmpeg_available: bool = False
    ffmpeg_nvdec: bool = False
    ffmpeg_nvenc: bool = False


TokenResponse.model_rebuild()
