from __future__ import annotations

import json
from pathlib import Path

from app.core.schemas import Detection
from scripts.evaluate_video_cases import build_parser, evaluate_video, main


KNOWN_VIDEO = "7894c9c171c6449194fcc8d5f0235cc4.mp4"


class FakeCapture:
    def __init__(self, frame_count: int) -> None:
        self.frame_count = frame_count
        self.index = 0
        self.released = False

    def isOpened(self) -> bool:
        return True

    def get(self, prop: int) -> float:
        return {
            FakeCV2.CAP_PROP_FRAME_COUNT: float(self.frame_count),
            FakeCV2.CAP_PROP_FPS: 25.0,
            FakeCV2.CAP_PROP_FRAME_WIDTH: 640.0,
            FakeCV2.CAP_PROP_FRAME_HEIGHT: 480.0,
        }[prop]

    def read(self):
        if self.index >= self.frame_count:
            return False, None
        self.index += 1
        return True, object()

    def release(self) -> None:
        self.released = True


class FakeCV2:
    CAP_PROP_FRAME_COUNT = 1
    CAP_PROP_FPS = 2
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self, frame_count: int = 477) -> None:
        self.frame_count = frame_count
        self.captures: list[FakeCapture] = []

    def VideoCapture(self, path: str) -> FakeCapture:
        capture = FakeCapture(self.frame_count)
        self.captures.append(capture)
        return capture


class FakeDetector:
    available = True
    backend = "fake-ultralytics"
    load_error = None

    def __init__(self, person_count: int = 3, transient_fourth: bool = False, **kwargs) -> None:
        self.person_count = person_count
        self.transient_fourth = transient_fourth

    def detect(self, frame, frame_index: int):
        detections = [
            Detection(
                class_name="person",
                confidence=0.9,
                bbox=[20 + index * 140, 40, 120 + index * 140, 430],
                frame_index=frame_index,
            )
            for index in range(self.person_count)
        ]
        if self.transient_fourth and frame_index in {198, 475, 476}:
            detections.append(
                Detection(
                    class_name="person",
                    confidence=0.51,
                    bbox=[500, 250, 570, 330],
                    frame_index=frame_index,
                )
            )
        return detections


def _video_file(tmp_path: Path) -> Path:
    video = tmp_path / KNOWN_VIDEO
    video.write_bytes(b"fake-video-for-unit-test")
    return video


def test_video_evaluator_uses_confirmation_and_records_known_key_frames(tmp_path: Path):
    video = _video_file(tmp_path)
    fake_cv2 = FakeCV2()

    result = evaluate_video(
        video,
        FakeDetector(person_count=3, transient_fourth=True),
        cv2_module=fake_cv2,
    )

    summaries = {item["frame_index"]: item for item in result["key_frames"]}
    assert result["metadata"]["processed_frame_count"] == 477
    assert result["confirmed_detection_counts"]["person"] == 3 * 475
    assert len(result["confirmed_tracks"]) == 3
    assert all(summaries[index]["confirmed_person_count"] == 3 for index in (198, 475, 476))
    assert all(item["passed"] for item in result["assertions"])
    assert result["assertions_passed"] is True
    assert fake_cv2.captures[0].released is True


def test_cli_returns_nonzero_and_writes_targeted_report_when_assertion_fails(tmp_path: Path):
    video = _video_file(tmp_path)
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"fake-weights-for-unit-test")
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--weights",
            str(weights),
            "--video",
            str(video),
            "--device",
            "cpu",
            "--imgsz",
            "640",
            "--output",
            str(output),
        ],
        detector_factory=lambda **kwargs: FakeDetector(person_count=4, **kwargs),
        cv2_module=FakeCV2(),
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["report_type"] == "targeted_video_regression"
    assert report["evaluation_scope"]["independent_generalization_metrics"] is False
    assert report["assertions_passed"] is False
    assert {item["actual"] for item in report["assertions"]} == {4}


def test_parser_accepts_repeated_and_grouped_video_arguments():
    args = build_parser().parse_args(
        ["--weights", "model.pt", "--video", "one.mp4", "two.mp4", "--video", "three.mp4"]
    )

    assert args.video_groups == [[Path("one.mp4"), Path("two.mp4")], [Path("three.mp4")]]
