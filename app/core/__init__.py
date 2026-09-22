"""Core inference, tracking, and safety-rule APIs."""

from .detector import FallbackDetector, YOLODetector
from .rules import RuleEngine, SafetyRuleEngine, associate_explicit_violations, associate_ppe, point_in_polygon
from .schemas import (
    BBox,
    BoundingBox,
    DangerZone,
    Detection,
    EventStatus,
    EventType,
    FrameResult,
    InferenceJob,
    InferenceResult,
    JobStatus,
    PPEAssociation,
    Point,
    SafetyEvent,
    Severity,
    SourceType,
)
from .tracker import ByteTrack, ByteTrackTracker, Tracker

__all__ = [
    "BBox",
    "BoundingBox",
    "ByteTrack",
    "ByteTrackTracker",
    "DangerZone",
    "Detection",
    "EventStatus",
    "EventType",
    "FallbackDetector",
    "FrameResult",
    "InferenceJob",
    "InferenceResult",
    "JobStatus",
    "PPEAssociation",
    "Point",
    "RuleEngine",
    "SafetyEvent",
    "SafetyRuleEngine",
    "Severity",
    "SourceType",
    "Tracker",
    "YOLODetector",
    "associate_explicit_violations",
    "associate_ppe",
    "point_in_polygon",
]
