"""Orchestrate the E8 acceptance checks without deploying weights.

The four checks are intentionally serial and stop on the first operational
failure or hard gate failure:

1. original merged-set ``test`` metrics (a same-split comparison, not a
   leakage-free independent test),
2. the three hard-case image assertions,
3. the two known video assertions, and
4. an eight-image smoke run (workflow coverage only).

This command never copies weights or changes the serving model.  It writes a
single JSON report that can be reviewed before any explicitly separate
deployment action.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_E7_METRICS = ROOT / "results" / "expanded-ppe-yolov8s-hardcase12-test-metrics.json"
DEFAULT_OUTPUT = ROOT / "results" / "e8-acceptance.json"
DEFAULT_EXPECTATIONS = ROOT / "data" / "hard_cases" / "regression_expectations.json"
DEFAULT_HARD_IMAGES = ROOT / "data" / "hard_cases" / "images" / "train"
DEFAULT_DEMO_IMAGES = ROOT / "data" / "demo" / "selected" / "images"
DEFAULT_VIDEO_1 = ROOT / "uploads" / "9dd0c7b9ae444314a01de70e3c3f5468.mp4"
DEFAULT_VIDEO_2 = ROOT / "uploads" / "7894c9c171c6449194fcc8d5f0235cc4.mp4"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E8 acceptance gates without deployment.")
    parser.add_argument("--weights", type=Path, required=True, help="E8 best.pt to evaluate")
    parser.add_argument("--e7-metrics", type=Path, default=DEFAULT_E7_METRICS)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "expanded_ppe_kaggle" / "dataset.yaml")
    parser.add_argument("--hard-images", type=Path, default=DEFAULT_HARD_IMAGES)
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--video", dest="videos", action="append", type=Path)
    parser.add_argument("--demo-images", type=Path, default=DEFAULT_DEMO_IMAGES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter used for child scripts")
    parser.add_argument("--device", default="0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--dry-run", action="store_true", help="Print steps and write no report")
    return parser


def _default_videos() -> list[Path]:
    return [DEFAULT_VIDEO_1, DEFAULT_VIDEO_2]


def build_steps(args: argparse.Namespace, output_dir: Path) -> list[dict[str, Any]]:
    """Return the exact child commands, with explicit output for every step."""

    weights = args.weights.resolve()
    video_paths = list(args.videos) if args.videos else _default_videos()
    metrics_output = output_dir / "e8-test-metrics.json"
    hard_output = output_dir / "e8-hardcase-regression.json"
    video_output = output_dir / "e8-video-regression.json"
    demo_output = output_dir / "e8-demo-smoke.json"
    py = str(args.python)
    common = ["--weights", str(weights), "--imgsz", str(args.imgsz), "--device", str(args.device)]
    return [
        {
            "name": "test_metrics",
            "hard_gate": True,
            "command": [
                py,
                str(ROOT / "scripts" / "evaluate_yolo.py"),
                *common,
                "--data",
                str(args.data.resolve()),
                "--split",
                "test",
                "--output",
                str(metrics_output),
            ],
            "output": metrics_output,
        },
        {
            "name": "hardcase_images",
            "hard_gate": True,
            "command": [
                py,
                str(ROOT / "scripts" / "evaluate_demo_set.py"),
                *common,
                "--images",
                str(args.hard_images.resolve()),
                "--pattern",
                "hard_??.jpg",
                "--expectations",
                str(args.expectations.resolve()),
                "--output",
                str(hard_output),
            ],
            "output": hard_output,
        },
        {
            "name": "video_regression",
            "hard_gate": True,
            "command": [
                py,
                str(ROOT / "scripts" / "evaluate_video_cases.py"),
                *common,
                *sum((["--video", str(path.resolve())] for path in video_paths), []),
                "--output",
                str(video_output),
            ],
            "output": video_output,
        },
        {
            "name": "demo_image_smoke",
            "hard_gate": False,
            "command": [
                py,
                str(ROOT / "scripts" / "evaluate_demo_set.py"),
                *common,
                "--images",
                str(args.demo_images.resolve()),
                "--output",
                str(demo_output),
            ],
            "output": demo_output,
        },
    ]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"report root must be an object: {path}")
    return payload


def compare_metrics(e8: dict[str, Any], e7: dict[str, Any]) -> dict[str, Any]:
    """Compare aggregate and known per-class metrics while preserving nulls."""

    comparison: dict[str, Any] = {"aggregate": {}, "per_class": {}}
    for key in ("precision", "recall", "f1", "map50", "map50_95"):
        new_value, old_value = e8.get(key), e7.get(key)
        comparison["aggregate"][key] = {
            "e8": new_value,
            "e7": old_value,
            "delta": round(new_value - old_value, 10) if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)) else None,
        }
    names = set((e8.get("per_class") or {}).keys()) | set((e7.get("per_class") or {}).keys())
    for name in sorted(names):
        new_row, old_row = (e8.get("per_class") or {}).get(name, {}), (e7.get("per_class") or {}).get(name, {})
        comparison["per_class"][name] = {}
        for key in ("precision", "recall", "f1", "map50"):
            new_value, old_value = new_row.get(key), old_row.get(key)
            comparison["per_class"][name][key] = {
                "e8": new_value,
                "e7": old_value,
                "delta": round(new_value - old_value, 10) if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)) else None,
            }
    return comparison


def _hard_gate_status(name: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    errors = payload.get("operational_errors")
    if errors:
        return False, f"{name}: operational_errors present"
    if name == "hardcase_images":
        passed = payload.get("passed") is True and payload.get("assertions_passed") is True
    elif name == "video_regression":
        passed = payload.get("assertions_passed") is True
    else:
        passed = True
    return bool(passed), None if passed else f"{name}: hard assertions failed"


def _metrics_status(payload: dict[str, Any]) -> tuple[bool, str | None]:
    required = ("precision", "recall", "f1", "map50", "map50_95", "per_class")
    missing = [key for key in required if key not in payload]
    if missing:
        return False, f"test_metrics: missing required fields: {', '.join(missing)}"
    if payload.get("split") not in (None, "test"):
        return False, f"test_metrics: expected split=test, got {payload.get('split')!r}"
    return True, None


def _smoke_status(payload: dict[str, Any]) -> dict[str, Any]:
    errors = payload.get("operational_errors") or []
    count = payload.get("image_count")
    return {
        "passed": not errors and count == 8,
        "image_count": count,
        "expected_image_count": 8,
        "operational_errors": errors,
        "is_accuracy_gate": False,
        "statement": "Eight built-in images are workflow smoke coverage only; no detection accuracy assertion is applied.",
    }


def run_acceptance(args: argparse.Namespace, *, runner: Any = subprocess.run) -> dict[str, Any]:
    output = args.output.resolve()
    output_dir = output.parent
    steps = build_steps(args, output_dir)
    report: dict[str, Any] = {
        "report_type": "e8_acceptance",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "weights": str(args.weights.resolve()),
        "execution": {"dry_run": bool(args.dry_run), "stopped_on_failure": True},
        "scope": {
            "test_comparison": "original merged-set test split comparison only; the split contains near-duplicate leakage and is not a leakage-free independent test",
            "hardcase_gate": "three known images; targeted regression only",
            "video_gate": "two known videos; targeted regression only",
            "demo_smoke": "eight images; workflow smoke only, not an accuracy gate",
        },
        "steps": [],
        "e7_metrics": None,
        "e8_metrics": None,
        "comparison": None,
        "decision": {"eligible_for_manual_review": False, "deployment": {"action": "none", "reason": "Acceptance never deploys or copies weights."}},
    }
    if args.dry_run:
        report["steps"] = [{"name": step["name"], "hard_gate": step["hard_gate"], "command": step["command"], "output": str(step["output"])} for step in steps]
        return report

    try:
        report["e7_metrics"] = _read_json(args.e7_metrics.resolve())
    except Exception as exc:
        report["decision"]["reason"] = f"cannot read E7 metrics: {exc}"
        report["steps"].append({"name": "load_e7_metrics", "status": "failed", "error": str(exc)})
        return report

    for step in steps:
        row: dict[str, Any] = {"name": step["name"], "hard_gate": step["hard_gate"], "command": step["command"], "output": str(step["output"]), "status": "running"}
        try:
            completed = runner(step["command"], cwd=str(ROOT), check=False, capture_output=True, text=True)
            row["returncode"] = int(completed.returncode)
            if completed.stdout:
                row["stdout_tail"] = completed.stdout[-2000:]
            if completed.stderr:
                row["stderr_tail"] = completed.stderr[-2000:]
            if completed.returncode != 0:
                row["status"] = "failed"
                report["steps"].append(row)
                break
            payload = _read_json(step["output"])
            row["result"] = payload
            row["status"] = "passed"
            if step["name"] == "test_metrics":
                ok, reason = _metrics_status(payload)
                row["gate_passed"] = ok
                if ok:
                    report["e8_metrics"] = payload
                    report["comparison"] = compare_metrics(payload, report["e7_metrics"])
                else:
                    row["status"], row["error"] = "failed", reason
            elif step["hard_gate"]:
                ok, reason = _hard_gate_status(step["name"], payload)
                row["gate_passed"] = ok
                if not ok:
                    row["status"], row["error"] = "failed", reason
            else:
                row["smoke"] = _smoke_status(payload)
                if not row["smoke"]["passed"]:
                    row["status"] = "failed"
            report["steps"].append(row)
            if row["status"] != "passed":
                break
        except Exception as exc:
            row["status"], row["error"] = "failed", str(exc)
            report["steps"].append(row)
            break

    hard_steps = [step for step in report["steps"] if step["name"] in {"test_metrics", "hardcase_images", "video_regression"}]
    all_passed = len(hard_steps) == 3 and all(step.get("status") == "passed" and step.get("gate_passed", True) for step in hard_steps)
    smoke = next((step.get("smoke") for step in report["steps"] if step["name"] == "demo_image_smoke"), None)
    report["decision"] = {
        "eligible_for_manual_review": bool(all_passed and smoke and smoke.get("passed")),
        "deployment": {"action": "none", "reason": "Acceptance never deploys or copies weights."},
    }
    return report


def main(argv: Sequence[str] | None = None, *, runner: Any = subprocess.run) -> int:
    args = build_parser().parse_args(argv)
    report = run_acceptance(args, runner=runner)
    if not args.dry_run:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    return 0 if report["decision"]["eligible_for_manual_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
