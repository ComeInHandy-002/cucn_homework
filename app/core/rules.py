"""Safety rule evaluation: PPE association, zones, confirmation and cooldown."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from .schemas import (
    DangerZone,
    Detection,
    EventStatus,
    EventType,
    PPEAssociation,
    Point,
    SafetyEvent,
    Severity,
)
from .tracker import canonical_class_name


def point_in_polygon(point: Point | Sequence[float], polygon: Iterable[Point | Sequence[float]]) -> bool:
    """Return whether a point is inside or on the boundary of a polygon.

    Ray casting is kept local to avoid making Shapely a mandatory dependency.
    Boundary points are considered inside, which is the safer interpretation
    for a worker standing exactly on a configured danger-zone edge.
    """

    p = Point.from_value(point)
    vertices = [Point.from_value(item) for item in polygon]
    if len(vertices) < 3:
        return False
    inside = False
    for index, current in enumerate(vertices):
        previous = vertices[index - 1]
        cross = (p.y - previous.y) * (current.x - previous.x) - (p.x - previous.x) * (current.y - previous.y)
        if abs(cross) <= 1e-9 and min(previous.x, current.x) <= p.x <= max(previous.x, current.x) and min(previous.y, current.y) <= p.y <= max(previous.y, current.y):
            return True
        intersects = (current.y > p.y) != (previous.y > p.y)
        if intersects:
            x_at_y = (previous.x - current.x) * (p.y - current.y) / (previous.y - current.y) + current.x
            if p.x < x_at_y:
                inside = not inside
    return inside


def associate_ppe(
    persons: Iterable[Detection],
    detections: Iterable[Detection],
    minimum_confidence: float = 0.0,
) -> dict[int, PPEAssociation]:
    """Associate helmet/vest boxes with the nearest compatible person.

    A PPE box is accepted when its center lies inside the person's box and in
    the expected body region.  The highest-confidence candidate wins for a
    person.  Untracked persons use negative deterministic keys (``-1, -2``).
    """

    person_list = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in persons]
    all_detections = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in detections]
    ppe = [item for item in all_detections if item.confidence >= minimum_confidence]
    associations: dict[int, PPEAssociation] = {}
    candidates_by_person: dict[int, dict[str, list[Detection]]] = {
        person.track_id if person.track_id is not None else -(index + 1): {"helmet": [], "vest": []}
        for index, person in enumerate(person_list)
    }
    # Assign each PPE box to one best-supported person.  With overlapping
    # person boxes, accepting the same box for every person can suppress a
    # genuine missing-PPE event on the neighbouring track.
    for detection in ppe:
        kind = canonical_class_name(detection.class_name)
        if kind not in {"helmet", "vest"}:
            continue
        center = detection.bbox.center
        eligible: list[tuple[float, float, int]] = []
        for index, person in enumerate(person_list):
            if not person.bbox.contains(center):
                continue
            relative_y = (center.y - person.bbox.y1) / max(person.bbox.height, 1e-9)
            if kind == "helmet" and relative_y > 0.40:
                continue
            if kind == "vest" and not 0.20 <= relative_y <= 0.85:
                continue
            person_key = person.track_id if person.track_id is not None else -(index + 1)
            # IoU is the primary signal; distance to the person centre breaks
            # ties when a small PPE box sits inside two nearby tracks.
            iou = person.bbox.iou(detection.bbox)
            dx = center.x - person.bbox.center.x
            dy = center.y - person.bbox.center.y
            distance = (dx * dx + dy * dy) ** 0.5 / max(person.bbox.width, person.bbox.height, 1.0)
            eligible.append((iou, -distance, person_key))
        if eligible:
            _, _, best_key = max(eligible)
            candidates_by_person[best_key][kind].append(detection)
    for index, person in enumerate(person_list):
        key = person.track_id if person.track_id is not None else -(index + 1)
        candidates = candidates_by_person[key]
        associations[key] = PPEAssociation(
            person=person,
            helmet=max(candidates["helmet"], key=lambda item: item.confidence, default=None),
            vest=max(candidates["vest"], key=lambda item: item.confidence, default=None),
        )
    return associations


def associate_explicit_violations(
    persons: Iterable[Detection],
    detections: Iterable[Detection],
    minimum_confidence: float = 0.0,
) -> dict[int, set[EventType]]:
    person_list = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in persons]
    all_detections = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in detections]
    explicit_classes = {"no_helmet": EventType.NO_HELMET, "no_vest": EventType.NO_VEST}
    flags: dict[int, set[EventType]] = {}
    for index, person in enumerate(person_list):
        person_key = person.track_id if person.track_id is not None else -(index + 1)
        flags[person_key] = set()
        for detection in all_detections:
            if detection.confidence < minimum_confidence:
                continue
            event_type = explicit_classes.get(canonical_class_name(detection.class_name))
            if event_type is not None and person.bbox.contains(detection.bbox.center):
                flags[person_key].add(event_type)
    return flags


class SafetyRuleEngine:
    """Evaluate frame detections and emit confirmed safety events."""

    def __init__(
        self,
        zones: Iterable[DangerZone | dict[str, Any]] = (),
        confirmation_frames: int = 3,
        cooldown_seconds: float = 10.0,
        minimum_confidence: float = 0.0,
        ppe_grace_frames: int = 0,
        ppe_warmup_frames: int = 0,
    ) -> None:
        if confirmation_frames < 1:
            raise ValueError("confirmation_frames must be at least 1")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        if ppe_grace_frames < 0 or ppe_warmup_frames < 0:
            raise ValueError("PPE grace and warmup frames cannot be negative")
        self.zones = [zone if isinstance(zone, DangerZone) else DangerZone.model_validate(zone) for zone in zones]
        self.confirmation_frames = int(confirmation_frames)
        self.cooldown = timedelta(seconds=float(cooldown_seconds))
        self.minimum_confidence = float(minimum_confidence)
        self.ppe_grace_frames = int(ppe_grace_frames)
        self.ppe_warmup_frames = int(ppe_warmup_frames)
        self._frame_counter = 0
        self._track_seen: dict[tuple[str | None, int], int] = {}
        # Store the last PPE observation in the track's own observation
        # sequence, rather than the global video frame counter.  A person can
        # disappear for several frames because of occlusion or a detector
        # dropout; those frames should not consume the PPE grace window.
        self._ppe_seen: dict[tuple[str | None, int, str], int] = {}
        self._consecutive: dict[tuple[str | None, int, EventType], int] = {}
        self._last_emitted: dict[tuple[str | None, int, EventType], datetime] = {}

    def reset(self) -> None:
        self._frame_counter = 0
        self._track_seen.clear()
        self._ppe_seen.clear()
        self._consecutive.clear()
        self._last_emitted.clear()

    @staticmethod
    def _timestamp(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _person_key(person: Detection, index: int) -> int:
        return person.track_id if person.track_id is not None else -(index + 1)

    def _is_in_zone(self, person: Detection, camera_id: str | None) -> DangerZone | None:
        point = person.bbox.bottom_center
        for zone in self.zones:
            if not zone.enabled or (zone.camera_id is not None and zone.camera_id != camera_id):
                continue
            if point_in_polygon(point, zone.polygon):
                return zone
        return None

    def _consider(
        self,
        event_type: EventType,
        person: Detection,
        person_key: int,
        camera_id: str | None,
        timestamp: datetime,
        evidence_path: str | None,
        zone: DangerZone | None = None,
    ) -> SafetyEvent | None:
        key = (camera_id, person_key, event_type)
        self._consecutive[key] = self._consecutive.get(key, 0) + 1
        if self._consecutive[key] < self.confirmation_frames:
            return None
        last_emitted = self._last_emitted.get(key)
        if last_emitted is not None and timestamp - last_emitted < self.cooldown:
            return None
        self._last_emitted[key] = timestamp
        severity = {
            EventType.NO_HELMET: Severity.HIGH,
            EventType.NO_VEST: Severity.MEDIUM,
            EventType.INTRUSION: Severity.CRITICAL,
        }[event_type]
        message = {
            EventType.NO_HELMET: "Worker is missing a safety helmet",
            EventType.NO_VEST: "Worker is missing a reflective vest",
            EventType.INTRUSION: "Worker entered a configured danger zone",
        }[event_type]
        return SafetyEvent(
            event_type=event_type,
            severity=severity,
            camera_id=camera_id,
            track_id=person.track_id,
            timestamp=timestamp,
            evidence_path=evidence_path,
            status=EventStatus.OPEN,
            zone_id=zone.id if zone else None,
            message=message,
            metadata={"confirmation_frames": self._consecutive[key]},
        )

    def evaluate_frame(
        self,
        detections: Iterable[Detection],
        camera_id: str | None = None,
        timestamp: datetime | None = None,
        evidence_path: str | None = None,
    ) -> list[SafetyEvent]:
        timestamp = self._timestamp(timestamp)
        self._frame_counter += 1
        parsed = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in detections]
        persons = [
            item for item in parsed if canonical_class_name(item.class_name) == "person" and item.confidence >= self.minimum_confidence
        ]
        associations = associate_ppe(persons, parsed, minimum_confidence=self.minimum_confidence)
        explicit_violations = associate_explicit_violations(persons, parsed, minimum_confidence=self.minimum_confidence)
        current_keys: set[tuple[str | None, int, EventType]] = set()
        events: list[SafetyEvent] = []
        for index, person in enumerate(persons):
            person_key = self._person_key(person, index)
            memory_key = (camera_id, person_key)
            seen_frames = self._track_seen.get(memory_key, 0) + 1
            self._track_seen[memory_key] = seen_frames
            association = associations[person_key]
            person_explicit = explicit_violations.get(person_key, set())
            has_helmet = association.has_helmet
            has_vest = association.has_vest
            if has_helmet:
                self._ppe_seen[(camera_id, person_key, "helmet")] = seen_frames
            if has_vest:
                self._ppe_seen[(camera_id, person_key, "vest")] = seen_frames
            # A detector can miss a small helmet/vest for a handful of video
            # observations while the tracked person remains stable.  Reuse the
            # last confirmed PPE state for that short interval.  The interval
            # is measured in observations of this person, not global video
            # frames, so occlusion does not turn uncertainty into an alert.
            if not has_helmet:
                last_seen = self._ppe_seen.get((camera_id, person_key, "helmet"))
                has_helmet = last_seen is not None and seen_frames - last_seen <= self.ppe_grace_frames
            if not has_vest:
                last_seen = self._ppe_seen.get((camera_id, person_key, "vest"))
                has_vest = last_seen is not None and seen_frames - last_seen <= self.ppe_grace_frames
            violations: list[tuple[EventType, DangerZone | None]] = []
            # Positive PPE evidence wins over a conflicting negative class in
            # the same frame (or during the grace interval).  A weak/ambiguous
            # ``no_helmet`` box must not turn a confirmed helmet into an alert.
            helmet_missing = not has_helmet
            vest_missing = not has_vest
            # Give a new video track enough observations for PPE association
            # before declaring a violation.  This does not affect intrusion
            # checks and is disabled for image mode by default.
            if seen_frames <= self.ppe_warmup_frames and not person_explicit:
                helmet_missing = False
                vest_missing = False
            if helmet_missing:
                violations.append((EventType.NO_HELMET, None))
            if vest_missing:
                violations.append((EventType.NO_VEST, None))
            zone = self._is_in_zone(person, camera_id)
            if zone is not None:
                violations.append((EventType.INTRUSION, zone))
            for event_type, event_zone in violations:
                key = (camera_id, person_key, event_type)
                current_keys.add(key)
                event = self._consider(event_type, person, person_key, camera_id, timestamp, evidence_path, event_zone)
                if event is not None:
                    events.append(event)

        # Missing a violation in a frame breaks consecutive confirmation.  Do
        # not clear last-emitted timestamps: cooldown still applies when it
        # reappears within the configured window.
        for key in list(self._consecutive):
            if key not in current_keys:
                del self._consecutive[key]
        return events

    # Short aliases for service and test code.
    evaluate = evaluate_frame
    process_frame = evaluate_frame


RuleEngine = SafetyRuleEngine
