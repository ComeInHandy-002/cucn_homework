from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.evaluate_demo_set import build_assertions, build_parser, load_expectations, main


class EmptyDetector:
    available = True
    load_error = None

    def __init__(self, **kwargs) -> None:
        pass

    def detect(self, frame, frame_index: int, *, strict_ppe: bool = False):
        return []


class FailingDetector(EmptyDetector):
    def detect(self, frame, frame_index: int, *, strict_ppe: bool = False):
        raise RuntimeError("synthetic inference failure")


def _image_file(directory: Path, name: str = "case.jpg") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    Image.new("RGB", (8, 8), color="white").save(path)
    return path


def _expectations_file(path: Path, *, expected_people: int = 1) -> Path:
    path.write_text(
        json.dumps(
            {
                "images": {
                    "case.jpg": {
                        "counts": {"person": {"exact": expected_people}},
                        "allowed_events": [],
                        "forbidden_events": ["no_helmet", "no_vest", "intrusion"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_assertions_support_count_ranges_and_event_allow_deny_lists():
    rows = [
        {
            "file": "case.jpg",
            "counts": {"person": 2, "helmet": 2, "vest": 1},
            "events": ["no_vest"],
        }
    ]
    expectations = {
        "images": {
            "case.jpg": {
                "counts": {
                    "person": {"min": 1, "max": 2},
                    "helmet": {"exact": 2},
                    "vest": 1,
                },
                "allowed_events": ["no_vest"],
                "forbidden_events": ["no_helmet", "intrusion"],
            }
        }
    }

    assertions = build_assertions(rows, expectations)

    assert len(assertions) == 7
    assert all(item["passed"] for item in assertions)
    assert {item["operator"] for item in assertions} >= {
        "present",
        "exact",
        "min",
        "max",
        "subset_of",
        "disjoint_from",
    }


def test_assertions_report_missing_images_bad_counts_and_forbidden_events():
    rows = [{"file": "case.jpg", "counts": {"person": 3}, "events": ["no_helmet"]}]
    expectations = {
        "images": {
            "case.jpg": {
                "counts": {"person": {"max": 2}},
                "allowed_events": ["no_vest"],
                "forbidden_events": ["no_helmet"],
            },
            "missing.jpg": {"counts": {"person": {"min": 1}}, "allowed_events": []},
        }
    }

    assertions = build_assertions(rows, expectations)
    failed_ids = {item["id"] for item in assertions if not item["passed"]}

    assert "case.jpg:count:person:max" in failed_ids
    assert "case.jpg:events:allowed" in failed_ids
    assert "case.jpg:events:forbidden" in failed_ids
    assert "missing.jpg:image-present" in failed_ids
    assert "missing.jpg:count:person:min" in failed_ids


def test_cli_returns_one_and_writes_targeted_report_on_assertion_failure(tmp_path: Path):
    images = tmp_path / "images"
    _image_file(images)
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"unit-test-weights")
    expectations = _expectations_file(tmp_path / "expectations.json")
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--weights",
            str(weights),
            "--images",
            str(images),
            "--expectations",
            str(expectations),
            "--output",
            str(output),
            "--device",
            "cpu",
        ],
        detector_factory=EmptyDetector,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["report_type"] == "targeted_image_regression"
    assert report["evaluation_scope"]["independent_generalization_metrics"] is False
    assert report["gate_enabled"] is True
    assert report["passed"] is False
    assert report["assertions_passed"] is False
    assert report["operational_errors"] == []


def test_cli_returns_zero_when_all_expectations_pass(tmp_path: Path):
    images = tmp_path / "images"
    _image_file(images)
    expectations = _expectations_file(tmp_path / "expectations.json", expected_people=0)
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--weights",
            "weights.pt",
            "--images",
            str(images),
            "--expectations",
            str(expectations),
            "--output",
            str(output),
        ],
        detector_factory=EmptyDetector,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["passed"] is True
    assert report["assertions_passed"] is True
    assert all(item["passed"] for item in report["assertions"])


def test_cli_returns_two_and_records_inference_errors(tmp_path: Path):
    images = tmp_path / "images"
    _image_file(images)
    output = tmp_path / "report.json"

    exit_code = main(
        ["--weights", "weights.pt", "--images", str(images), "--output", str(output)],
        detector_factory=FailingDetector,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["passed"] is False
    assert report["operational_errors"] == [
        {"file": str(images / "case.jpg"), "error": "synthetic inference failure"}
    ]


def test_parser_keeps_original_cli_and_accepts_optional_expectations():
    args = build_parser().parse_args(
        [
            "--weights",
            "model.pt",
            "--images",
            "images",
            "--pattern",
            "hard_??.jpg",
            "--imgsz",
            "960",
            "--device",
            "cpu",
            "--output",
            "report.json",
            "--expectations",
            "expectations.json",
        ]
    )

    assert args.weights == "model.pt"
    assert args.pattern == "hard_??.jpg"
    assert args.expectations == Path("expectations.json")


def test_hard_case_manifest_is_valid_and_covers_three_original_images():
    path = Path("data/hard_cases/regression_expectations.json")

    expectations = load_expectations(path)

    assert set(expectations["images"]) == {"hard_01.jpg", "hard_02.jpg", "hard_03.jpg"}
