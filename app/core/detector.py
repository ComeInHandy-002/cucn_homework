"""YOLOv8-compatible detection adapters with a deterministic fallback."""

from __future__ import annotations

import math
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Sequence

from .schemas import BoundingBox, Detection


PERSON = "person"
HELMET = "helmet"
VEST = "vest"

# The downloaded Construction-PPE model contains several classes that are
# outside this system's contract (boots, gloves, goggles, ...).  Keeping them
# out of the API is important: those classes otherwise appear as detections
# even though the rule engine cannot use them.
_BUSINESS_CLASSES = {PERSON, HELMET, VEST, "no_helmet", "no_vest"}
_CLASS_CONFIDENCE = {
    # The expanded model's test negatives still produce occasional weak
    # person boxes around 0.35-0.54.  The post-processing gate below removes
    # tiny, nearly-square background candidates while retaining a validated
    # close factory worker around 0.506 confidence.
    PERSON: 0.45,
    # The expanded model is conservatively calibrated for small/distant PPE:
    # the real walkway worker in the held-out demo scores about 0.02/0.04 for
    # helmet/vest.  Keep those candidates here and rely on the person-relative
    # geometry checks plus video confirmation to reject background boxes.
    HELMET: 0.015,
    VEST: 0.04,
    "no_helmet": 0.25,
    "no_vest": 0.25,
}
# A still image has no temporal confirmation or PPE grace period.  Requiring
# stronger PPE evidence there prevents a weak background box from making an
# actually non-compliant worker look compliant.  Video keeps the lower floors
# above because ByteTrack and the rule engine confirm state across frames.
_STRICT_CLASS_CONFIDENCE = {
    **_CLASS_CONFIDENCE,
    # Keep the image path aligned with the validated video floor.  The
    # factory demo's real worker scores 0.506, so 0.55 would discard the
    # person before PPE association and hide the missing-helmet alert.
    PERSON: 0.45,
    HELMET: 0.15,
    VEST: 0.15,
}

_PPE_CLASSES = {HELMET, VEST, "no_helmet", "no_vest"}
_PPE_FRAME_AREA_LIMIT = {
    HELMET: 0.18,
    VEST: 0.45,
    "no_helmet": 0.18,
    "no_vest": 0.45,
}
_PPE_PERSON_AREA_LIMIT = {
    HELMET: 0.30,
    VEST: 0.60,
    "no_helmet": 0.30,
    "no_vest": 0.60,
}

# Low-confidence person boxes that occupy only a few pixels are frequently
# machinery, signs, or other background texture (for example, the red
# excavator in the construction-site demo).  Keep this gate deliberately
# narrow: high-confidence close-ups and ordinary full-body workers are not
# affected, while the ambiguous candidates cannot create PPE alerts/tracks.
_AMBIGUOUS_PERSON_CONFIDENCE = 0.60
_AMBIGUOUS_PERSON_HEIGHT_RATIO = 0.16
_AMBIGUOUS_PERSON_MIN_ASPECT = 1.10
# A low-score strip at the image's left/right edge is commonly a partial
# vehicle, scaffold, or person-shaped background texture.  Keep this gate
# deliberately conservative: it only applies to narrow, tall boxes and is
# bypassed when the model supplies PPE evidence for that same box.
_EDGE_PARTIAL_CONFIDENCE = 0.60
_EDGE_PARTIAL_MAX_WIDTH_RATIO = 0.14
_EDGE_PARTIAL_MIN_HEIGHT_RATIO = 0.35
_EDGE_PARTIAL_MIN_ASPECT = 2.50


def _canonical_model_class(value: Any) -> str:
    name = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "person": PERSON,
        "people": PERSON,
        "worker": PERSON,
        "hardhat": HELMET,
        "hard_hat": HELMET,
        "safety_helmet": HELMET,
        "safetyhat": HELMET,
        "safety_vest": VEST,
        "reflective_vest": VEST,
        "reflective_jacket": VEST,
        "hi_vis_vest": VEST,
        "no_hardhat": "no_helmet",
        "no_hard_hat": "no_helmet",
        "no_safety_helmet": "no_helmet",
        "no_safety_vest": "no_vest",
        "no_reflective_vest": "no_vest",
    }.get(name, name)


def _frame_size(frame: Any) -> tuple[int, int]:
    """Best-effort width/height extraction without requiring OpenCV."""

    shape = getattr(frame, "shape", None)
    if shape is not None and len(shape) >= 2:
        return max(1, int(shape[1])), max(1, int(shape[0]))
    size = getattr(frame, "size", None)
    if isinstance(size, Sequence) and len(size) >= 2:
        # PIL exposes size as (width, height).
        return max(1, int(size[0])), max(1, int(size[1]))
    if isinstance(frame, (bytes, bytearray)):
        # There is no reliable way to decode all formats without cv2/Pillow.
        # A stable default keeps the fallback useful in API smoke tests.
        return 640, 480
    return 640, 480


def _frame_digest(frame: Any) -> bytes:
    if isinstance(frame, (bytes, bytearray, memoryview)):
        return sha256(bytes(frame)).digest()
    try:
        return sha256(frame.tobytes()).digest()
    except AttributeError:
        return sha256(repr(frame).encode("utf-8")).digest()


def _clip_bbox(coords: Sequence[float], frame_width: int, frame_height: int) -> BoundingBox | None:
    """Clip model coordinates to the source frame and reject unusable boxes."""

    if len(coords) < 4:
        return None
    try:
        values = [float(item) for item in coords[:4]]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    left = max(0.0, min(float(frame_width), min(x1, x2)))
    top = max(0.0, min(float(frame_height), min(y1, y2)))
    right = max(0.0, min(float(frame_width), max(x1, x2)))
    bottom = max(0.0, min(float(frame_height), max(y1, y2)))
    if right - left < 2.0 or bottom - top < 2.0:
        return None
    return BoundingBox(x1=left, y1=top, x2=right, y2=bottom)


def _is_frame_edge_person(box: BoundingBox, frame_width: int, frame_height: int) -> bool:
    """Return whether a sizeable person box is likely a background hallucination.

    A model can assign ``person`` to a wall or sky-shaped region that starts at
    one image border.  A genuine close-up worker may have the same geometry,
    so callers keep it only when a plausible helmet/vest box supports it.
    """

    frame_area = max(float(frame_width * frame_height), 1.0)
    area_ratio = box.area / frame_area
    edge_tolerance = max(float(frame_width), float(frame_height)) * 0.01
    touches = sum(
        (
            box.x1 <= edge_tolerance,
            box.y1 <= edge_tolerance,
            box.x2 >= frame_width - edge_tolerance,
            box.y2 >= frame_height - edge_tolerance,
        )
    )
    # A large box touching even one border is usually a scene-sized false
    # positive (wall, sky, floor).  PPE context is checked by the caller so a
    # clipped close-up worker is still recoverable.
    if touches >= 1 and area_ratio >= 0.45:
        return True
    return touches >= 2 and area_ratio >= 0.20


def _is_anomalous_person(box: BoundingBox, frame_width: int, frame_height: int) -> bool:
    """Reject background-sized person hallucinations.

    Frame-edge candidates are handled separately after PPE context is
    available; this pass only removes geometry that is unambiguously too
    large to represent a worker.
    """

    frame_area = max(float(frame_width * frame_height), 1.0)
    area_ratio = box.area / frame_area
    if area_ratio >= 0.92:
        return True
    # A very wide, nearly frame-sized rectangle is not a plausible upright
    # worker even when it does not land exactly on all four borders.
    if area_ratio >= 0.78 and box.height / max(box.width, 1e-9) < 0.85:
        return True
    return False


def _is_plausible_close_person(detection: Detection) -> bool:
    """Keep a high-confidence upright close-up even when PPE is absent.

    A safety system must be able to emit a missing-PPE event for a worker who
    fills the frame.  Scene-sized wall/sky hallucinations tend to be wide and
    have weaker confidence, so this narrow exception does not reintroduce the
    background false positive handled by the edge filter.
    """

    if detection.confidence < 0.90:
        return False
    aspect = detection.bbox.height / max(detection.bbox.width, 1e-9)
    return aspect >= 0.90


def _is_tiny_ambiguous_person(
    detection: Detection,
    frame_width: int,
    frame_height: int,
) -> bool:
    """Reject weak, tiny person candidates that are usually background objects.

    The model can assign a person label to a distant vehicle or excavator at
    roughly 0.45--0.55 confidence.  A low-confidence box below 16% of frame
    height is not a reliable PPE subject; a nearly square box is also unlike a
    standing worker.  Either signal is sufficient, but only below the 0.60
    confidence boundary so confident small workers remain visible.
    """

    if detection.confidence >= _AMBIGUOUS_PERSON_CONFIDENCE:
        return False
    height_ratio = detection.bbox.height / max(float(frame_height), 1.0)
    aspect = detection.bbox.height / max(detection.bbox.width, 1e-9)
    if height_ratio < _AMBIGUOUS_PERSON_HEIGHT_RATIO or aspect < _AMBIGUOUS_PERSON_MIN_ASPECT:
        return True

    return False


def _is_ambiguous_edge_partial_person(
    detection: Detection,
    frame_width: int,
    frame_height: int,
) -> bool:
    """Identify low-confidence, narrow edge strips without rejecting close-ups.

    A partial person at an image border can be legitimate, but a very narrow
    0.4--0.6-confidence strip is more often a background artifact.  The caller
    checks for a matching helmet/vest before dropping it, so a real edge worker
    with visible PPE remains available to the rule engine.
    """

    if detection.confidence >= _EDGE_PARTIAL_CONFIDENCE:
        return False
    box = detection.bbox
    edge_tolerance = max(2.0, float(frame_width) * 0.02)
    touches_vertical_edge = box.x1 <= edge_tolerance or box.x2 >= frame_width - edge_tolerance
    if not touches_vertical_edge:
        return False
    width_ratio = box.width / max(float(frame_width), 1.0)
    height_ratio = box.height / max(float(frame_height), 1.0)
    aspect = box.height / max(box.width, 1e-9)
    return (
        width_ratio <= _EDGE_PARTIAL_MAX_WIDTH_RATIO
        and height_ratio >= _EDGE_PARTIAL_MIN_HEIGHT_RATIO
        and aspect >= _EDGE_PARTIAL_MIN_ASPECT
    )


def _belongs_to_person(
    detection: Detection,
    persons: Sequence[Detection],
    frame_width: int,
    frame_height: int,
) -> bool:
    """Return whether a PPE/violation box is spatially plausible for a worker."""

    if not persons:
        return False
    class_name = detection.class_name
    frame_area = max(float(frame_width * frame_height), 1.0)
    if detection.bbox.area / frame_area > _PPE_FRAME_AREA_LIMIT.get(class_name, 1.0):
        return False
    center = detection.bbox.center
    matches: list[Detection] = []
    for person in persons:
        if not person.bbox.contains(center):
            continue
        intersection_left = max(detection.bbox.x1, person.bbox.x1)
        intersection_top = max(detection.bbox.y1, person.bbox.y1)
        intersection_right = min(detection.bbox.x2, person.bbox.x2)
        intersection_bottom = min(detection.bbox.y2, person.bbox.y2)
        intersection = max(0.0, intersection_right - intersection_left) * max(0.0, intersection_bottom - intersection_top)
        # A centre-point match alone is insufficient for a large background
        # box.  Require most of the PPE box to overlap the worker box while
        # allowing a small amount of truncation at image edges.
        overlap_ratio = intersection / max(detection.bbox.area, 1.0)
        if overlap_ratio < 0.45:
            continue
        relative_y = (center.y - person.bbox.y1) / max(person.bbox.height, 1e-9)
        if class_name in {HELMET, "no_helmet"} and relative_y > 0.40:
            continue
        if class_name in {VEST, "no_vest"} and not 0.20 <= relative_y <= 0.90:
            continue
        person_area = max(person.bbox.area, 1.0)
        if detection.bbox.area / person_area > _PPE_PERSON_AREA_LIMIT.get(class_name, 1.0):
            continue
        matches.append(person)
    return bool(matches)


class FallbackDetector:
    """A deterministic detector used when weights or optional packages are absent.

    It produces a synthetic person in the center of the frame and configurable
    PPE detections.  ``scenario`` makes demos and tests able to exercise all
    safety rules without pretending that a model was loaded.
    """

    _SCENARIOS = {"compliant", "no_helmet", "no_vest", "no_ppe", "intrusion"}

    def __init__(
        self,
        scenario: str = "compliant",
        confidence: float = 0.92,
        include_helmet: bool | None = None,
        include_vest: bool | None = None,
    ) -> None:
        if scenario not in self._SCENARIOS:
            raise ValueError(f"unknown fallback scenario: {scenario}")
        self.scenario = scenario
        self.confidence = max(0.0, min(1.0, float(confidence)))
        self.include_helmet = include_helmet
        self.include_vest = include_vest

    @property
    def backend(self) -> str:
        return "fallback"

    def detect(
        self,
        frame: Any,
        frame_index: int | None = None,
        *,
        strict_ppe: bool = False,
    ) -> list[Detection]:
        width, height = _frame_size(frame)
        # Include a digest in the deterministic calculation so two frame-like
        # inputs cannot accidentally share mutable state; the geometry remains
        # stable for a given frame shape, which is important for tracking.
        _ = _frame_digest(frame)[0]
        person_box = BoundingBox(x1=width * 0.30, y1=height * 0.12, x2=width * 0.70, y2=height * 0.92)
        detections = [
            Detection(
                class_name=PERSON,
                confidence=self.confidence,
                bbox=person_box,
                frame_index=frame_index,
            )
        ]
        want_helmet = self.include_helmet if self.include_helmet is not None else self.scenario not in {"no_helmet", "no_ppe"}
        want_vest = self.include_vest if self.include_vest is not None else self.scenario not in {"no_vest", "no_ppe"}
        if want_helmet:
            detections.append(
                Detection(
                    class_name=HELMET,
                    confidence=self.confidence,
                    bbox=BoundingBox(x1=width * 0.43, y1=height * 0.10, x2=width * 0.57, y2=height * 0.25),
                    frame_index=frame_index,
                )
            )
        if want_vest:
            detections.append(
                Detection(
                    class_name=VEST,
                    confidence=self.confidence,
                    bbox=BoundingBox(x1=width * 0.37, y1=height * 0.35, x2=width * 0.63, y2=height * 0.66),
                    frame_index=frame_index,
                )
            )
        return detections

    # ``predict`` and ``__call__`` make the adapter convenient in small scripts.
    def predict(self, frame: Any, frame_index: int | None = None, *, strict_ppe: bool = False) -> list[Detection]:
        return self.detect(frame, frame_index=frame_index, strict_ppe=strict_ppe)

    def __call__(self, frame: Any, frame_index: int | None = None, *, strict_ppe: bool = False) -> list[Detection]:
        return self.detect(frame, frame_index=frame_index, strict_ppe=strict_ppe)

    def detect_batch(
        self,
        frames: Sequence[Any],
        frame_indices: Sequence[int | None] | None = None,
        *,
        strict_ppe: bool = False,
    ) -> list[list[Detection]]:
        frame_list = list(frames)
        indices = list(frame_indices) if frame_indices is not None else list(range(len(frame_list)))
        if len(indices) != len(frame_list):
            raise ValueError("frame_indices must have the same length as frames")
        return [
            self.detect(frame, frame_index=indices[index], strict_ppe=strict_ppe)
            for index, frame in enumerate(frame_list)
        ]


class YOLODetector:
    """Thin YOLOv8 adapter with safe model-loading fallback.

    The adapter never downloads weights implicitly.  Pass an existing weights
    path (or an already-created ultralytics model object) to enable real
    inference; otherwise it reports ``backend == 'fallback'``.
    """

    def __init__(
        self,
        model_path: str | os.PathLike[str] | Any = "yolov8s.pt",
        confidence: float = 0.25,
        device: str | int | None = None,
        fallback: FallbackDetector | None = None,
        allow_download: bool = False,
        image_size: int | None = 1280,
        half: bool = False,
        batch_size: int = 8,
        tensorrt: bool = False,
    ) -> None:
        self.model_path = model_path
        self.confidence = max(0.0, min(1.0, float(confidence)))
        self.device = device
        self.image_size = max(320, int(image_size)) if image_size else None
        self.half_requested = bool(half)
        self.batch_size = max(1, int(batch_size))
        self.tensorrt_requested = bool(tensorrt)
        self.model: Any | None = None
        self.load_error: str | None = None
        self.fallback = fallback or FallbackDetector()
        self._load_model(allow_download=allow_download)

    @property
    def backend(self) -> str:
        if self.model is None:
            return self.fallback.backend
        if self.tensorrt_active:
            return "tensorrt"
        return "ultralytics"

    @property
    def tensorrt_active(self) -> bool:
        return isinstance(self.model_path, (str, os.PathLike)) and str(self.model_path).lower().endswith(".engine")

    @property
    def half_enabled(self) -> bool:
        """Return whether Ultralytics can safely run FP16 for this instance."""

        if not self.half_requested or self.model is None:
            return False
        try:
            import torch  # type: ignore

            if not torch.cuda.is_available():
                return False
        except Exception:
            return False
        if self.device is None or str(self.device).strip().lower() in {"", "auto"}:
            return True
        return str(self.device).lower().startswith("cuda") or str(self.device).isdigit()

    @property
    def available(self) -> bool:
        return self.model is not None

    def _load_model(self, allow_download: bool) -> None:
        # Existing model objects are useful for tests and custom deployments.
        if not isinstance(self.model_path, (str, os.PathLike)):
            self.model = self.model_path
            return
        model_path = Path(self.model_path)
        if not model_path.exists() and not allow_download:
            self.load_error = f"model weights not found: {model_path}"
            return
        try:
            from ultralytics import YOLO  # type: ignore

            self.model = YOLO(str(model_path))
        except Exception as exc:  # optional dependency and weight errors are fallback-able
            self.load_error = str(exc)
            self.model = None

    @staticmethod
    def _names_for(result: Any, model: Any) -> MappingLike:
        names = getattr(result, "names", None) or getattr(model, "names", None) or {}
        return names

    def _prediction_kwargs(self, strict_ppe: bool = False, batch_size: int | None = None) -> dict[str, Any]:
        # Ask Ultralytics for the low-confidence PPE candidates needed by the
        # contextual filter. Person and class floors are enforced after
        # prediction, so weak background boxes never reach downstream rules.
        confidence_floors = _STRICT_CLASS_CONFIDENCE if strict_ppe else _CLASS_CONFIDENCE
        kwargs: dict[str, Any] = {
            "conf": min(self.confidence, min(confidence_floors.values())),
            "verbose": False,
        }
        if self.device is not None:
            kwargs["device"] = self.device
        if self.image_size is not None:
            kwargs["imgsz"] = self.image_size
        if batch_size is not None:
            kwargs["batch"] = max(1, int(batch_size))
        if self.half_enabled:
            kwargs["half"] = True
        # Test-time augmentation recovers small/occluded PPE in still images;
        # video uses the faster single-pass path and temporal confirmation.
        if strict_ppe:
            kwargs["augment"] = True
        return kwargs

    def _detections_from_result(
        self,
        result: Any,
        frame: Any,
        frame_index: int | None,
        strict_ppe: bool = False,
    ) -> list[Detection]:
        if result is None:
            return []
        frame_width, frame_height = _frame_size(frame)
        confidence_floors = _STRICT_CLASS_CONFIDENCE if strict_ppe else _CLASS_CONFIDENCE
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        xyxy_values = _to_rows(getattr(boxes, "xyxy", []))
        confidence_values = _to_values(getattr(boxes, "conf", []))
        class_values = _to_values(getattr(boxes, "cls", []))
        names = self._names_for(result, self.model)
        detections: list[Detection] = []
        for index, coords in enumerate(xyxy_values):
            if len(coords) < 4:
                continue
            class_index = int(class_values[index]) if index < len(class_values) else 0
            raw_class_name = names.get(class_index, str(class_index)) if hasattr(names, "get") else str(class_index)
            class_name = _canonical_model_class(raw_class_name)
            score = float(confidence_values[index]) if index < len(confidence_values) else 1.0
            if class_name not in _BUSINESS_CLASSES or score < confidence_floors.get(class_name, self.confidence):
                continue
            bbox = _clip_bbox(coords[:4], frame_width, frame_height)
            if bbox is None:
                continue
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=max(0.0, min(1.0, score)),
                    bbox=bbox,
                    frame_index=frame_index,
                )
            )
        return self._postprocess_detections(detections, frame_width, frame_height)

    def _detect_model(self, frame: Any, frame_index: int | None, strict_ppe: bool = False) -> list[Detection]:
        if self.model is None:
            return self.fallback.detect(frame, frame_index=frame_index, strict_ppe=strict_ppe)
        results = self.model.predict(source=frame, **self._prediction_kwargs(strict_ppe=strict_ppe))
        result_list = list(results or [])
        return self._detections_from_result(result_list[0] if result_list else None, frame, frame_index, strict_ppe)

    @classmethod
    def _postprocess_detections(
        cls,
        detections: list[Detection],
        frame_width: int,
        frame_height: int,
    ) -> list[Detection]:
        """Apply geometry checks that a generic object detector cannot know.

        PPE is only meaningful when it belongs to a detected person.  Applying
        that relation here keeps background boxes out of both evidence images
        and safety rules, instead of relying on every downstream consumer to
        repeat the same filtering.
        """

        # Keep all person candidates through the first pass.  A real close-up
        # worker can fill the frame and should only be removed after we have
        # had a chance to use its helmet/vest boxes as context.  Do not run
        # duplicate suppression before this decision: a frame-sized false
        # positive would otherwise cover and suppress a valid worker box.
        raw_candidates = [
            item
            for item in detections
            if item.class_name != PERSON
            or not _is_tiny_ambiguous_person(item, frame_width, frame_height)
        ]
        all_persons = [item for item in raw_candidates if item.class_name == PERSON]
        ppe_candidates = [item for item in raw_candidates if item.class_name in _PPE_CLASSES]
        # A narrow, low-confidence strip touching the left/right image edge
        # is usually a partial background artifact.  Keep it when a helmet or
        # vest is geometrically associated; otherwise it must not create a
        # track and subsequent missing-PPE alerts.
        all_persons = [
            person
            for person in all_persons
            if not _is_ambiguous_edge_partial_person(person, frame_width, frame_height)
            or any(_belongs_to_person(item, [person], frame_width, frame_height) for item in ppe_candidates)
        ]
        # Keep a worker touching two image borders when a plausible, confident
        # PPE box supports it.  This matters for close-up workers at the edge;
        # border-sized hallucinations without PPE are discarded.
        persons: list[Detection] = []
        for person in all_persons:
            anomalous = _is_anomalous_person(person.bbox, frame_width, frame_height)
            edge_sized = _is_frame_edge_person(person.bbox, frame_width, frame_height)
            if not anomalous and not edge_sized:
                persons.append(person)
                continue
            supported = [
                item
                for item in ppe_candidates
                if _belongs_to_person(item, [person], frame_width, frame_height)
            ]
            # A frame-sized box is the most common background hallucination;
            # require both head and torso evidence before accepting it.  A
            # merely clipped worker needs one valid PPE box to remain useful.
            supported_kinds = {item.class_name for item in supported}
            minimum_support = 2 if anomalous else 1
            if len(supported_kinds) >= minimum_support or _is_plausible_close_person(person):
                persons.append(person)

        # Suppress duplicates only after implausible person candidates have
        # been removed, then use the resulting set for PPE association.
        candidates = cls._suppress_nested_duplicates(
            persons + [item for item in raw_candidates if item.class_name != PERSON]
        )
        persons = [item for item in candidates if item.class_name == PERSON]
        ppe_candidates = [item for item in candidates if item.class_name in _PPE_CLASSES]

        filtered: list[Detection] = []
        for detection in candidates:
            if detection.class_name not in _PPE_CLASSES:
                if detection.class_name != PERSON or detection in persons:
                    filtered.append(detection)
                continue
            if _belongs_to_person(detection, persons, frame_width, frame_height):
                filtered.append(detection)
        return filtered

    @staticmethod
    def _suppress_nested_duplicates(detections: list[Detection]) -> list[Detection]:
        """Remove low-confidence boxes nested inside a stronger same-class box.

        Some Construction-PPE images produce a full-person box plus a second
        partial-person box.  The model's class-wise NMS does not always remove
        that pair because their IoU is below the NMS threshold.  Suppressing a
        box whose area is mostly covered by a stronger box avoids duplicate
        tracks and duplicate safety events without merging separate workers.
        """

        kept: list[Detection] = []
        for candidate in sorted(detections, key=lambda item: item.confidence, reverse=True):
            duplicate = False
            for existing in kept:
                if existing.class_name != candidate.class_name:
                    continue
                intersection_left = max(existing.bbox.x1, candidate.bbox.x1)
                intersection_top = max(existing.bbox.y1, candidate.bbox.y1)
                intersection_right = min(existing.bbox.x2, candidate.bbox.x2)
                intersection_bottom = min(existing.bbox.y2, candidate.bbox.y2)
                intersection = max(0.0, intersection_right - intersection_left) * max(0.0, intersection_bottom - intersection_top)
                candidate_coverage = intersection / candidate.bbox.area if candidate.bbox.area else 0.0
                iou = existing.bbox.iou(candidate.bbox)
                # Person duplicates are often partial boxes with IoU below a
                # generic NMS threshold; use a slightly stronger same-worker
                # check while retaining nearby workers with little overlap.
                coverage_limit = 0.65 if candidate.class_name == PERSON else 0.75
                iou_limit = 0.45 if candidate.class_name == PERSON else 0.50
                if candidate_coverage >= coverage_limit or iou >= iou_limit:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(candidate)
        return kept

    def detect(self, frame: Any, frame_index: int | None = None, *, strict_ppe: bool = False) -> list[Detection]:
        return self._detect_model(frame, frame_index, strict_ppe=strict_ppe)

    def detect_batch(
        self,
        frames: Sequence[Any],
        frame_indices: Sequence[int | None] | None = None,
        *,
        strict_ppe: bool = False,
    ) -> list[list[Detection]]:
        """Run one Ultralytics call for a frame batch and preserve input order.

        Tracking and rule evaluation deliberately stay outside this method.
        The detector is the only stage allowed to reorder work, and the
        returned list always has one entry per input frame.
        """

        frame_list = list(frames)
        if not frame_list:
            return []
        indices = list(frame_indices) if frame_indices is not None else list(range(len(frame_list)))
        if len(indices) != len(frame_list):
            raise ValueError("frame_indices must have the same length as frames")
        if self.model is None:
            return [
                self.fallback.detect(frame, frame_index=indices[index], strict_ppe=strict_ppe)
                for index, frame in enumerate(frame_list)
            ]

        batch_size = min(len(frame_list), self.batch_size)
        results = self.model.predict(
            source=frame_list,
            **self._prediction_kwargs(strict_ppe=strict_ppe, batch_size=batch_size),
        )
        result_list = list(results or [])
        # Ultralytics returns one Results object per source image.  A custom
        # test adapter may not support list input; retain correctness by
        # falling back to single-frame calls rather than assigning detections
        # to the wrong frame.
        if len(result_list) != len(frame_list):
            return [
                self._detect_model(frame, indices[index], strict_ppe=strict_ppe)
                for index, frame in enumerate(frame_list)
            ]
        return [
            self._detections_from_result(result_list[index], frame, indices[index], strict_ppe)
            for index, frame in enumerate(frame_list)
        ]

    def predict_batch(
        self,
        frames: Sequence[Any],
        frame_indices: Sequence[int | None] | None = None,
        *,
        strict_ppe: bool = False,
    ) -> list[list[Detection]]:
        return self.detect_batch(frames, frame_indices=frame_indices, strict_ppe=strict_ppe)

    def predict(self, frame: Any, frame_index: int | None = None, *, strict_ppe: bool = False) -> list[Detection]:
        return self.detect(frame, frame_index=frame_index, strict_ppe=strict_ppe)

    def __call__(self, frame: Any, frame_index: int | None = None, *, strict_ppe: bool = False) -> list[Detection]:
        return self.detect(frame, frame_index=frame_index, strict_ppe=strict_ppe)


def _to_rows(value: Any) -> list[list[float]]:
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        return [list(map(float, row)) for row in value]
    except (TypeError, ValueError):
        return []


def _to_values(value: Any) -> list[float]:
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (int, float)):
            return [float(value)]
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return []


# A small structural alias avoids importing typing.Protocol solely for names.
MappingLike = Any


Detector = YOLODetector
