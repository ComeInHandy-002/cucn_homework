"""Run reproducible, targeted regression checks over selected images.

This report verifies known cases only. Independent precision, recall and mAP
must still be measured on a held-out test split with ``evaluate_yolo.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image

# Running a script by path makes ``scripts`` the first import location. Add
# the repository root explicitly so the regression command is self-contained.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.detector import YOLODetector
from app.core.rules import SafetyRuleEngine
from app.core.tracker import ByteTrackTracker


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a YOLO weight on the curated demo image set.")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--images", type=Path, default=ROOT / "data" / "demo" / "selected" / "images")
    parser.add_argument("--pattern", default="*", help="Image filename glob, for example hard_??.jpg")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--expectations",
        type=Path,
        default=None,
        help="Optional JSON gate with per-file count and event expectations.",
    )
    return parser


def _enum_value(value: Any) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _nonnegative_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{location} must be a non-negative integer")
    return value


def _event_list(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{location} must be a list of non-empty strings")
    return list(dict.fromkeys(value))


def load_expectations(path: Path) -> dict[str, Any]:
    """Load and validate the small, intentionally explicit gate schema."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid expectations JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("expectations root must be a JSON object")
    images = payload.get("images")
    if not isinstance(images, dict) or not images:
        raise ValueError("expectations.images must be a non-empty object keyed by filename")

    for filename, spec in images.items():
        location = f"expectations.images[{filename!r}]"
        if not isinstance(filename, str) or not filename:
            raise ValueError("expectation filenames must be non-empty strings")
        if not isinstance(spec, dict):
            raise ValueError(f"{location} must be an object")

        counts = spec.get("counts", {})
        if not isinstance(counts, dict):
            raise ValueError(f"{location}.counts must be an object")
        for class_name, constraint in counts.items():
            count_location = f"{location}.counts[{class_name!r}]"
            if not isinstance(class_name, str) or not class_name:
                raise ValueError(f"{location}.counts keys must be non-empty strings")
            if isinstance(constraint, int) and not isinstance(constraint, bool):
                _nonnegative_int(constraint, count_location)
                continue
            if not isinstance(constraint, dict) or not constraint:
                raise ValueError(f"{count_location} must be an integer or an object with min/max/exact")
            unknown = set(constraint) - {"min", "max", "exact"}
            if unknown:
                raise ValueError(f"{count_location} contains unsupported keys: {sorted(unknown)}")
            if "exact" in constraint and len(constraint) != 1:
                raise ValueError(f"{count_location}.exact cannot be combined with min or max")
            values = {
                operator: _nonnegative_int(expected, f"{count_location}.{operator}")
                for operator, expected in constraint.items()
            }
            if values.get("min", 0) > values.get("max", values.get("min", 0)):
                raise ValueError(f"{count_location}.min cannot exceed max")

        allowed = _event_list(spec.get("allowed_events", []), f"{location}.allowed_events")
        forbidden = _event_list(spec.get("forbidden_events", []), f"{location}.forbidden_events")
        overlap = sorted(set(allowed) & set(forbidden))
        if overlap:
            raise ValueError(f"{location} lists events as both allowed and forbidden: {overlap}")
    return payload


def _count_constraints(constraint: Any) -> list[tuple[str, int]]:
    if isinstance(constraint, int):
        return [("exact", constraint)]
    return [(operator, int(constraint[operator])) for operator in ("exact", "min", "max") if operator in constraint]


def build_assertions(
    rows: Sequence[Mapping[str, Any]],
    expectations: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate validated per-file expectations against serialized rows."""

    rows_by_file = {str(row["file"]): row for row in rows}
    assertions: list[dict[str, Any]] = []
    for filename, spec in expectations["images"].items():
        row = rows_by_file.get(filename)
        present = row is not None
        assertions.append(
            {
                "id": f"{filename}:image-present",
                "file": filename,
                "subject": "image",
                "operator": "present",
                "expected": True,
                "actual": present,
                "passed": present,
            }
        )
        counts = row.get("counts", {}) if row else {}
        for class_name, constraint in spec.get("counts", {}).items():
            actual = int(counts.get(class_name, 0)) if present else None
            for operator, expected in _count_constraints(constraint):
                passed = present and actual is not None
                if operator == "exact":
                    passed = passed and actual == expected
                elif operator == "min":
                    passed = passed and actual >= expected
                else:
                    passed = passed and actual <= expected
                assertions.append(
                    {
                        "id": f"{filename}:count:{class_name}:{operator}",
                        "file": filename,
                        "subject": f"counts.{class_name}",
                        "operator": operator,
                        "expected": expected,
                        "actual": actual,
                        "passed": passed,
                    }
                )

        actual_events = sorted({_enum_value(item) for item in row.get("events", [])}) if row else []
        if "allowed_events" in spec:
            allowed = sorted(set(spec["allowed_events"]))
            unexpected = sorted(set(actual_events) - set(allowed))
            assertions.append(
                {
                    "id": f"{filename}:events:allowed",
                    "file": filename,
                    "subject": "events",
                    "operator": "subset_of",
                    "expected": allowed,
                    "actual": actual_events,
                    "unexpected_events": unexpected,
                    "passed": present and not unexpected,
                }
            )
        if "forbidden_events" in spec:
            forbidden = sorted(set(spec["forbidden_events"]))
            violations = sorted(set(actual_events) & set(forbidden))
            assertions.append(
                {
                    "id": f"{filename}:events:forbidden",
                    "file": filename,
                    "subject": "events",
                    "operator": "disjoint_from",
                    "expected": forbidden,
                    "actual": actual_events,
                    "violating_events": violations,
                    "passed": present and not violations,
                }
            )
    return assertions


def evaluate_image(image_path: Path, detector: Any) -> dict[str, Any]:
    with Image.open(image_path) as source:
        frame = source.convert("RGB")
    detections = detector.detect(frame, frame_index=0, strict_ppe=True)
    tracked = ByteTrackTracker().update(detections, frame_index=0)
    events = SafetyRuleEngine(confirmation_frames=1).evaluate_frame(tracked)
    counts = Counter(item.class_name for item in detections)
    return {
        "file": image_path.name,
        "detections": [
            {
                "class_name": item.class_name,
                "confidence": round(float(item.confidence), 6),
                "bbox": item.bbox.model_dump(mode="json"),
                "track_id": item.track_id,
            }
            for item in tracked
        ],
        "counts": dict(sorted(counts.items())),
        "events": [_enum_value(event.event_type) for event in events],
    }


def _empty_report(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "report_type": "targeted_image_regression",
        "evaluation_scope": {
            "kind": "targeted_regression_only",
            "independent_generalization_metrics": False,
            "statement": (
                "This report checks selected known image cases only. It is not an independent "
                "precision/recall/mAP evaluation and must not be used as a generalization claim."
            ),
        },
        "weights": str(Path(args.weights)),
        "images": str(args.images.resolve()),
        "pattern": args.pattern,
        "imgsz": args.imgsz,
        "device": str(args.device),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "image_count": 0,
        "totals": {},
        "images_detail": [],
        "gate_enabled": args.expectations is not None,
        "expectations": str(args.expectations.resolve()) if args.expectations else None,
        "assertions": [],
        "assertions_passed": False,
        "passed": False,
        "operational_errors": [],
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] = YOLODetector,
) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or ROOT / "results" / f"demo-regression-{Path(args.weights).stem}.json"
    report = _empty_report(args)
    totals: Counter[str] = Counter()
    expectations: dict[str, Any] | None = None

    try:
        if args.expectations is not None:
            expectations = load_expectations(args.expectations)
        detector = detector_factory(
            model_path=args.weights,
            confidence=0.25,
            device=args.device,
            image_size=args.imgsz,
        )
        if hasattr(detector, "available") and not bool(detector.available):
            detail = getattr(detector, "load_error", None) or "unknown model loading error"
            raise RuntimeError(f"YOLO weights could not be loaded: {detail}")

        for image_path in sorted(args.images.glob(args.pattern)):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                row = evaluate_image(image_path, detector)
                report["images_detail"].append(row)
                totals.update(row["counts"])
            except Exception as exc:
                report["operational_errors"].append({"file": str(image_path), "error": str(exc)})
    except Exception as exc:
        report["operational_errors"].append({"file": None, "error": str(exc)})

    report["image_count"] = len(report["images_detail"])
    report["totals"] = dict(sorted(totals.items()))
    if expectations is not None:
        report["assertions"] = build_assertions(report["images_detail"], expectations)
    report["assertions_passed"] = all(item["passed"] for item in report["assertions"])
    report["passed"] = not report["operational_errors"] and report["assertions_passed"]

    try:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Unable to write regression report: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["operational_errors"]:
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
