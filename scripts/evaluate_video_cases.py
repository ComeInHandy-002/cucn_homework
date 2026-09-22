"""Run reproducible, targeted regression checks over selected videos.

This script intentionally reports targeted case behavior, not independent
model-quality metrics.  Independent precision/recall/mAP must be measured on
the held-out test split with ``scripts/evaluate_yolo.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.core.detector import YOLODetector
from app.core.rules import SafetyRuleEngine
from app.core.schemas import Detection, SafetyEvent
from app.core.tracker import ByteTrackTracker


PIPELINE_SETTINGS = {
    "tracker": {"min_confirmed_hits": 3},
    "rules": {
        "confirmation_frames": 3,
        "cooldown_seconds": 10.0,
        "ppe_grace_frames": 15,
        "ppe_warmup_frames": 15,
    },
}

# Frame indexes are zero-based, matching ``InferenceService._process_video``.
KNOWN_VIDEO_ASSERTIONS: dict[str, dict[str, Any]] = {
    "7894c9c171c6449194fcc8d5f0235cc4.mp4": {
        "key_frames": (198, 475, 476),
        "max_confirmed_persons": 3,
    }
}

_TIMELINE_ORIGIN = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _enum_value(value: Any) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _serialize_detection(detection: Detection) -> dict[str, Any]:
    return {
        "class_name": detection.class_name,
        "confidence": round(float(detection.confidence), 6),
        "bbox": detection.bbox.model_dump(mode="json"),
        "track_id": detection.track_id,
    }


def _serialize_event(event: SafetyEvent) -> dict[str, Any]:
    payload = event.model_dump(mode="json")
    payload["event_type"] = _enum_value(event.event_type)
    payload["status"] = _enum_value(event.status)
    payload["severity"] = _enum_value(event.severity)
    return payload


def _selected_key_frames(video_name: str, reported_frames: int) -> list[int]:
    selected: set[int] = set()
    if reported_frames > 0:
        selected.update((0, reported_frames // 2, reported_frames - 1))
    assertion = KNOWN_VIDEO_ASSERTIONS.get(video_name.lower())
    if assertion:
        selected.update(int(index) for index in assertion["key_frames"])
    return sorted(index for index in selected if index >= 0)


def _update_track_summary(
    tracks: dict[int, dict[str, Any]],
    detections: Sequence[Detection],
    frame_index: int,
) -> None:
    for detection in detections:
        if detection.class_name.lower() != "person" or detection.track_id is None:
            continue
        row = tracks.setdefault(
            detection.track_id,
            {
                "track_id": detection.track_id,
                "first_confirmed_frame": frame_index,
                "last_confirmed_frame": frame_index,
                "confirmed_observations": 0,
                "max_confidence": 0.0,
            },
        )
        row["last_confirmed_frame"] = frame_index
        row["confirmed_observations"] += 1
        row["max_confidence"] = max(float(row["max_confidence"]), float(detection.confidence))


def _key_frame_summary(
    frame_index: int,
    detections: Sequence[Detection],
    events: Sequence[SafetyEvent],
) -> dict[str, Any]:
    counts = Counter(item.class_name for item in detections)
    person_tracks = sorted(
        item.track_id
        for item in detections
        if item.class_name.lower() == "person" and item.track_id is not None
    )
    return {
        "frame_index": frame_index,
        "available": True,
        "confirmed_detection_counts": dict(sorted(counts.items())),
        "confirmed_person_count": counts.get("person", 0),
        "confirmed_person_track_ids": person_tracks,
        "detections": [_serialize_detection(item) for item in detections],
        "events": [_serialize_event(item) for item in events],
    }


def _build_assertions(video_name: str, summaries: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    spec = KNOWN_VIDEO_ASSERTIONS.get(video_name.lower())
    if spec is None:
        return []
    maximum = int(spec["max_confirmed_persons"])
    assertions: list[dict[str, Any]] = []
    for frame_index in spec["key_frames"]:
        summary = summaries.get(int(frame_index))
        available = bool(summary and summary["available"])
        actual = int(summary["confirmed_person_count"]) if available else None
        assertions.append(
            {
                "id": f"{video_name}:frame-{frame_index}:confirmed-person-count-lte-{maximum}",
                "frame_index": int(frame_index),
                "subject": "confirmed_person_count",
                "operator": "less_than_or_equal",
                "expected_maximum": maximum,
                "actual": actual,
                "frame_available": available,
                "passed": available and actual is not None and actual <= maximum,
            }
        )
    return assertions


def evaluate_video(
    video_path: Path,
    detector: Any,
    *,
    cv2_module: Any | None = None,
) -> dict[str, Any]:
    """Evaluate one complete video through the service-equivalent pipeline."""

    if cv2_module is None:
        try:
            import cv2 as cv2_module  # type: ignore[no-redef]
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            raise RuntimeError("OpenCV is required for video regression evaluation") from exc

    video_path = video_path.resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"video not found: {video_path}")

    cap = cv2_module.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"unable to open video: {video_path}")

    reported_frames = max(0, int(cap.get(cv2_module.CAP_PROP_FRAME_COUNT) or 0))
    fps = float(cap.get(cv2_module.CAP_PROP_FPS) or 25.0)
    if fps <= 0:
        fps = 25.0
    width = max(0, int(cap.get(cv2_module.CAP_PROP_FRAME_WIDTH) or 0))
    height = max(0, int(cap.get(cv2_module.CAP_PROP_FRAME_HEIGHT) or 0))
    selected_frames = _selected_key_frames(video_path.name, reported_frames)
    selected_set = set(selected_frames)

    tracker = ByteTrackTracker(**PIPELINE_SETTINGS["tracker"])
    rules = SafetyRuleEngine(zones=[], **PIPELINE_SETTINGS["rules"])
    raw_counts: Counter[str] = Counter()
    confirmed_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    tracks: dict[int, dict[str, Any]] = {}
    key_summaries: dict[int, dict[str, Any]] = {}
    event_rows: list[dict[str, Any]] = []
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            raw = detector.detect(frame, frame_index=frame_index)
            raw_counts.update(item.class_name for item in raw)
            confirmed = tracker.update(raw, frame_index=frame_index)
            confirmed_counts.update(item.class_name for item in confirmed)
            _update_track_summary(tracks, confirmed, frame_index)

            # Video-time timestamps make cooldown behavior reproducible across
            # fast and slow machines while retaining the service's 10s rule.
            timestamp = _TIMELINE_ORIGIN + timedelta(seconds=frame_index / fps)
            events = rules.evaluate_frame(confirmed, camera_id=None, timestamp=timestamp)
            for event in events:
                event_type = _enum_value(event.event_type)
                event_counts[event_type] += 1
                row = _serialize_event(event)
                row["frame_index"] = frame_index
                event_rows.append(row)
            if frame_index in selected_set:
                key_summaries[frame_index] = _key_frame_summary(frame_index, confirmed, events)
            frame_index += 1
    finally:
        cap.release()

    for selected in selected_frames:
        key_summaries.setdefault(
            selected,
            {
                "frame_index": selected,
                "available": False,
                "confirmed_detection_counts": {},
                "confirmed_person_count": None,
                "confirmed_person_track_ids": [],
                "detections": [],
                "events": [],
            },
        )

    assertions = _build_assertions(video_path.name, key_summaries)
    track_rows = sorted(tracks.values(), key=lambda item: int(item["track_id"]))
    for row in track_rows:
        row["max_confidence"] = round(float(row["max_confidence"]), 6)
    return {
        "video": str(video_path),
        "file_name": video_path.name,
        "sha256": _file_sha256(video_path),
        "metadata": {
            "reported_frame_count": reported_frames,
            "processed_frame_count": frame_index,
            "fps": fps,
            "width": width,
            "height": height,
            "duration_seconds": round(frame_index / fps, 6),
            "frame_index_base": 0,
        },
        "raw_detection_counts": dict(sorted(raw_counts.items())),
        "confirmed_detection_counts": dict(sorted(confirmed_counts.items())),
        "confirmed_tracks": track_rows,
        "event_counts": dict(sorted(event_counts.items())),
        "events": event_rows,
        "key_frames": [key_summaries[index] for index in sorted(key_summaries)],
        "assertions": assertions,
        "assertions_passed": all(item["passed"] for item in assertions),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run targeted video regressions through the production-equivalent inference pipeline."
    )
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument(
        "--video",
        dest="video_groups",
        required=True,
        action="append",
        nargs="+",
        type=Path,
        help="One or more videos; repeat --video or list multiple paths after it.",
    )
    parser.add_argument("--device", default="0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _flatten_video_groups(groups: Sequence[Sequence[Path]]) -> list[Path]:
    return [path for group in groups for path in group]


def _empty_report(weights: Path, device: str, imgsz: int) -> dict[str, Any]:
    return {
        "report_type": "targeted_video_regression",
        "evaluation_scope": {
            "kind": "targeted_regression_only",
            "independent_generalization_metrics": False,
            "statement": (
                "This report checks selected known video cases only. It is not an independent "
                "precision/recall/mAP evaluation and must not be used as a generalization claim."
            ),
        },
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "weights": {"path": str(weights.resolve()), "sha256": None},
        "runtime": {"device": str(device), "imgsz": int(imgsz), "confidence": settings.model_confidence},
        "pipeline_settings": PIPELINE_SETTINGS,
        "videos": [],
        "assertions": [],
        "assertions_passed": False,
        "operational_errors": [],
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] = YOLODetector,
    cv2_module: Any | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    videos = _flatten_video_groups(args.video_groups)
    output = args.output or ROOT / "results" / f"video-regression-{args.weights.stem}.json"
    report = _empty_report(args.weights, args.device, args.imgsz)

    try:
        if not args.weights.is_file():
            raise FileNotFoundError(f"weights not found: {args.weights.resolve()}")
        report["weights"]["sha256"] = _file_sha256(args.weights)
        detector = detector_factory(
            model_path=str(args.weights),
            confidence=settings.model_confidence,
            device=args.device,
            image_size=args.imgsz,
            allow_download=False,
        )
        if not bool(getattr(detector, "available", False)):
            detail = getattr(detector, "load_error", None) or "unknown model loading error"
            raise RuntimeError(f"YOLO weights could not be loaded: {detail}")
        report["runtime"]["detector_backend"] = getattr(detector, "backend", "unknown")

        for video_path in videos:
            try:
                result = evaluate_video(video_path, detector, cv2_module=cv2_module)
                report["videos"].append(result)
                report["assertions"].extend(
                    {"video": result["file_name"], **assertion} for assertion in result["assertions"]
                )
            except Exception as exc:
                report["operational_errors"].append({"video": str(video_path), "error": str(exc)})
    except Exception as exc:
        report["operational_errors"].append({"video": None, "error": str(exc)})

    report["assertions_passed"] = (
        not report["operational_errors"]
        and all(item["passed"] for item in report["assertions"])
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["operational_errors"]:
        return 2
    return 0 if report["assertions_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
