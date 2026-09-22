"""Shared, dependency-light schemas for the safety monitoring pipeline.

The core package deliberately only depends on Pydantic.  Model inference and
tracking implementations can be swapped without changing the API payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for persisted events."""

    return datetime.now(timezone.utc)


class EventType(str, Enum):
    NO_HELMET = "no_helmet"
    NO_VEST = "no_vest"
    INTRUSION = "intrusion"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class SourceType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAMERA = "camera"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Point(BaseModel):
    """A 2D image or polygon coordinate."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float

    @classmethod
    def from_value(cls, value: Any) -> "Point":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls.model_validate(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
            return cls(x=float(value[0]), y=float(value[1]))
        raise ValueError("point must be a mapping with x/y or a two-item sequence")


class BoundingBox(BaseModel):
    """An xyxy bounding box in source-image pixel coordinates."""

    model_config = ConfigDict(extra="forbid")

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def validate_order(self) -> "BoundingBox":
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("x2/y2 must be greater than or equal to x1/y1")
        return self

    @classmethod
    def from_value(cls, value: Any) -> "BoundingBox":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            # Accept the common ``xyxy`` key used by detector integrations.
            if "xyxy" in value:
                return cls.from_value(value["xyxy"])
            return cls.model_validate(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 4:
            return cls(x1=float(value[0]), y1=float(value[1]), x2=float(value[2]), y2=float(value[3]))
        raise ValueError("bbox must be a mapping or a four-item sequence")

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(x=(self.x1 + self.x2) / 2.0, y=(self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> Point:
        return Point(x=(self.x1 + self.x2) / 2.0, y=self.y2)

    def contains(self, point: Point | Sequence[float]) -> bool:
        p = Point.from_value(point)
        return self.x1 <= p.x <= self.x2 and self.y1 <= p.y <= self.y2

    def iou(self, other: "BoundingBox") -> float:
        left = max(self.x1, other.x1)
        top = max(self.y1, other.y1)
        right = min(self.x2, other.x2)
        bottom = min(self.y2, other.y2)
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2


# The short alias is useful when integrating libraries which call this type BBox.
BBox = BoundingBox


class Detection(BaseModel):
    """A model detection before or after tracking."""

    model_config = ConfigDict(extra="allow")

    class_name: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bbox: BoundingBox
    track_id: int | None = None
    frame_index: int | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox", mode="before")
    @classmethod
    def parse_bbox(cls, value: Any) -> BoundingBox:
        return BoundingBox.from_value(value)

    @field_validator("class_name", mode="before")
    @classmethod
    def normalise_class_name(cls, value: Any) -> str:
        return str(value).strip()

    def with_track(self, track_id: int | None) -> "Detection":
        return self.model_copy(update={"track_id": track_id})


class DangerZone(BaseModel):
    """A configurable polygon in source-image coordinates."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str = "Danger zone"
    camera_id: str | None = None
    polygon: list[Point] = Field(min_length=3)
    enabled: bool = True

    @field_validator("polygon", mode="before")
    @classmethod
    def parse_polygon(cls, value: Iterable[Any]) -> list[Point]:
        points = [Point.from_value(item) for item in value]
        if len(points) < 3:
            raise ValueError("a danger zone requires at least three points")
        return points


class PPEAssociation(BaseModel):
    """PPE found for one person detection."""

    model_config = ConfigDict(extra="allow")

    person: Detection
    helmet: Detection | None = None
    vest: Detection | None = None

    @property
    def has_helmet(self) -> bool:
        return self.helmet is not None

    @property
    def has_vest(self) -> bool:
        return self.vest is not None


class SafetyEvent(BaseModel):
    """A confirmed and emitted safety violation."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    event_type: EventType | str
    severity: Severity | str = Severity.MEDIUM
    camera_id: str | None = None
    track_id: int | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    evidence_path: str | None = None
    status: EventStatus = EventStatus.OPEN
    zone_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalise_timestamp(cls, value: Any) -> datetime:
        if value is None:
            return utc_now()
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return value


class InferenceJob(BaseModel):
    """Progress and result state for image/video inference."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    source_type: SourceType | str
    status: JobStatus = JobStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    result_path: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class FrameResult(BaseModel):
    """Structured output for one processed frame."""

    frame_index: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=utc_now)
    detections: list[Detection] = Field(default_factory=list)
    events: list[SafetyEvent] = Field(default_factory=list)


class InferenceResult(BaseModel):
    """Structured output for an image or completed video job."""

    job_id: str | None = None
    source_type: SourceType | str
    frames: list[FrameResult] = Field(default_factory=list)
    detections: list[Detection] = Field(default_factory=list)
    events: list[SafetyEvent] = Field(default_factory=list)
    result_path: str | None = None
    preview_path: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
