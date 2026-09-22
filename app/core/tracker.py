"""ByteTrack-compatible lightweight multi-object tracker.

The real ByteTrack package is optional.  This implementation performs the
high-value part needed by the project (stable person IDs) using greedy IoU
matching and a configurable lost-track window, so the service remains usable
on a CPU-only installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .schemas import Detection


def canonical_class_name(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "human": "person",
        "people": "person",
        "hardhat": "helmet",
        "hard_hat": "helmet",
        "safety_helmet": "helmet",
        "safetyhat": "helmet",
        "safety_vest": "vest",
        "reflective_vest": "vest",
        "reflective_jacket": "vest",
        "hi_vis_vest": "vest",
        "workwear": "vest",
        "uniform": "vest",
        "no_hardhat": "no_helmet",
        "no_hard_hat": "no_helmet",
        "no_safety_helmet": "no_helmet",
        "no_safety_vest": "no_vest",
        "no_reflective_vest": "no_vest",
    }
    return aliases.get(value, value)


@dataclass
class _Track:
    track_id: int
    class_name: str
    bbox: object
    last_frame: int
    missed: int = 0
    consecutive_hits: int = 1
    confirmed: bool = False


class ByteTrackTracker:
    """Stable-ID tracker with a ByteTrack-like update contract."""

    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_age: int = 30,
        track_classes: Iterable[str] = ("person",),
        start_id: int = 1,
        min_confirmed_hits: int = 1,
    ) -> None:
        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be between 0 and 1")
        if min_confirmed_hits < 1:
            raise ValueError("min_confirmed_hits must be at least 1")
        self.iou_threshold = float(iou_threshold)
        self.max_age = max(0, int(max_age))
        self.track_classes = {canonical_class_name(item) for item in track_classes}
        self.min_confirmed_hits = int(min_confirmed_hits)
        self._next_id = int(start_id)
        self._tracks: dict[int, _Track] = {}
        self._last_frame = -1

    @property
    def active_tracks(self) -> dict[int, Detection]:
        return {
            track_id: Detection(class_name=track.class_name, confidence=1.0, bbox=track.bbox, track_id=track_id)
            for track_id, track in self._tracks.items()
        }

    def reset(self) -> None:
        self._next_id = 1
        self._tracks.clear()
        self._last_frame = -1

    def _frame_number(self, frame_index: int | None) -> int:
        if frame_index is None:
            return self._last_frame + 1
        frame_number = int(frame_index)
        if frame_number < self._last_frame:
            # A restarted stream should not silently match IDs from the old one.
            self.reset()
        return frame_number

    def update(self, detections: Iterable[Detection], frame_index: int | None = None) -> list[Detection]:
        frame_number = self._frame_number(frame_index)
        parsed = [item if isinstance(item, Detection) else Detection.model_validate(item) for item in detections]
        eligible: list[tuple[int, Detection]] = [
            (index, det) for index, det in enumerate(parsed) if canonical_class_name(det.class_name) in self.track_classes
        ]
        unmatched_tracks = set(self._tracks)
        matched: dict[int, int] = {}

        # Greedy highest-IoU matching is deterministic and adequate for this
        # service's person tracking.  Ties resolve by track and detection order.
        candidates: list[tuple[float, int, int]] = []
        for detection_index, detection in eligible:
            for track_id, track in self._tracks.items():
                if canonical_class_name(track.class_name) == canonical_class_name(detection.class_name):
                    candidates.append((track.bbox.iou(detection.bbox), track_id, detection_index))
        for overlap, track_id, detection_index in sorted(candidates, key=lambda item: (-item[0], item[1], item[2])):
            if overlap < self.iou_threshold or track_id not in unmatched_tracks or detection_index in matched:
                continue
            matched[detection_index] = track_id
            unmatched_tracks.remove(track_id)

        output = list(parsed)
        for detection_index, detection in eligible:
            track_id = matched.get(detection_index)
            if track_id is None:
                track_id = self._next_id
                self._next_id += 1
                consecutive_hits = 1
                confirmed = consecutive_hits >= self.min_confirmed_hits
            else:
                previous = self._tracks[track_id]
                consecutive_hits = (
                    previous.consecutive_hits + 1
                    if previous.missed == 0 and frame_number == previous.last_frame + 1
                    else 1
                )
                confirmed = previous.confirmed or consecutive_hits >= self.min_confirmed_hits
            output[detection_index] = detection.with_track(track_id).model_copy(update={"frame_index": frame_number})
            self._tracks[track_id] = _Track(
                track_id=track_id,
                class_name=detection.class_name,
                bbox=detection.bbox,
                last_frame=frame_number,
                missed=0,
                consecutive_hits=consecutive_hits,
                confirmed=confirmed,
            )

        for track_id in list(unmatched_tracks):
            track = self._tracks[track_id]
            track.missed += max(1, frame_number - track.last_frame)
            track.last_frame = frame_number
            if track.missed > self.max_age:
                del self._tracks[track_id]

        self._last_frame = frame_number
        if self.min_confirmed_hits == 1:
            return output
        return self._confirmed_output(output)

    def _confirmed_output(self, detections: list[Detection]) -> list[Detection]:
        current_tracks = [
            detection
            for detection in detections
            if detection.track_id is not None
            and canonical_class_name(detection.class_name) in self.track_classes
        ]
        confirmed_ids = {
            detection.track_id
            for detection in current_tracks
            if self._tracks[detection.track_id].confirmed
        }
        output: list[Detection] = []
        for detection in detections:
            class_name = canonical_class_name(detection.class_name)
            if class_name in self.track_classes:
                if detection.track_id in confirmed_ids:
                    output.append(detection)
                continue
            if class_name in {"helmet", "vest", "no_helmet", "no_vest"}:
                associated_track_id = self._associated_track_id(detection, current_tracks)
                if associated_track_id in confirmed_ids:
                    output.append(detection)
                continue
            output.append(detection)
        return output

    @staticmethod
    def _associated_track_id(detection: Detection, persons: list[Detection]) -> int | None:
        class_name = canonical_class_name(detection.class_name)
        center = detection.bbox.center
        candidates: list[tuple[float, float, int]] = []
        for person in persons:
            if person.track_id is None or not person.bbox.contains(center):
                continue
            relative_y = (center.y - person.bbox.y1) / max(person.bbox.height, 1e-9)
            if class_name in {"helmet", "no_helmet"} and relative_y > 0.40:
                continue
            if class_name in {"vest", "no_vest"} and not 0.20 <= relative_y <= 0.90:
                continue
            dx = center.x - person.bbox.center.x
            dy = center.y - person.bbox.center.y
            distance = (dx * dx + dy * dy) ** 0.5 / max(person.bbox.width, person.bbox.height, 1.0)
            candidates.append((person.bbox.iou(detection.bbox), -distance, person.track_id))
        return max(candidates)[2] if candidates else None

    # Common naming used by ByteTrack integrations.
    track = update


ByteTrack = ByteTrackTracker
Tracker = ByteTrackTracker
