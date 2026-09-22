from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.run_e8_acceptance import build_parser, compare_metrics, main, run_acceptance


def _args(tmp_path: Path, *extra: str):
    return build_parser().parse_args(
        [
            "--weights",
            str(tmp_path / "e8-best.pt"),
            "--e7-metrics",
            str(tmp_path / "e7.json"),
            "--output",
            str(tmp_path / "acceptance.json"),
            *extra,
        ]
    )


def _payloads(tmp_path: Path, *, hard_pass: bool = True, video_pass: bool = True, smoke_count: int = 8):
    metrics = {"precision": 0.8, "recall": 0.7, "f1": 0.75, "map50": 0.72, "map50_95": 0.45, "per_class": {"helmet": {"recall": 0.5}}}
    e7 = {"precision": 0.79, "recall": 0.66, "f1": 0.72, "map50": 0.71, "map50_95": 0.44, "per_class": {"helmet": {"recall": 0.45}}}
    (tmp_path / "e7.json").write_text(json.dumps(e7), encoding="utf-8")
    return [
        metrics,
        {"passed": hard_pass, "assertions_passed": hard_pass, "operational_errors": []},
        {"assertions_passed": video_pass, "operational_errors": []},
        {"image_count": smoke_count, "operational_errors": []},
    ]


class FakeRunner:
    def __init__(self, output_dir: Path, payloads, fail_at: int | None = None):
        self.output_dir = output_dir
        self.payloads = payloads
        self.fail_at = fail_at
        self.calls: list[list[str]] = []

    def __call__(self, command, **kwargs):
        index = len(self.calls)
        self.calls.append(list(command))
        if self.fail_at == index:
            return subprocess.CompletedProcess(command, 7, stdout="", stderr="synthetic failure")
        output = Path(command[command.index("--output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.payloads[index]), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")


def test_compare_metrics_preserves_delta_and_class_metrics():
    result = compare_metrics({"precision": 0.8, "per_class": {"helmet": {"recall": 0.5}}}, {"precision": 0.7, "per_class": {"helmet": {"recall": 0.4}}})
    assert result["aggregate"]["precision"]["delta"] == 0.1
    assert result["per_class"]["helmet"]["recall"]["delta"] == 0.1


def test_acceptance_runs_four_steps_and_never_deploys(tmp_path: Path):
    args = _args(tmp_path)
    runner = FakeRunner(tmp_path, _payloads(tmp_path))
    report = run_acceptance(args, runner=runner)
    assert [item["name"] for item in report["steps"]] == ["test_metrics", "hardcase_images", "video_regression", "demo_image_smoke"]
    assert report["decision"]["eligible_for_manual_review"] is True
    assert report["decision"]["deployment"]["action"] == "none"
    assert len(runner.calls) == 4


def test_hard_gate_failure_stops_before_later_steps(tmp_path: Path):
    args = _args(tmp_path)
    runner = FakeRunner(tmp_path, _payloads(tmp_path, hard_pass=False))
    report = run_acceptance(args, runner=runner)
    assert [item["name"] for item in report["steps"]] == ["test_metrics", "hardcase_images"]
    assert report["decision"]["eligible_for_manual_review"] is False


def test_smoke_is_not_accuracy_gate_and_wrong_count_fails_review(tmp_path: Path):
    args = _args(tmp_path)
    runner = FakeRunner(tmp_path, _payloads(tmp_path, smoke_count=7))
    report = run_acceptance(args, runner=runner)
    smoke = report["steps"][-1]["smoke"]
    assert smoke["is_accuracy_gate"] is False
    assert smoke["passed"] is False
    assert report["decision"]["eligible_for_manual_review"] is False


def test_dry_run_prints_commands_without_running_or_writing_report(tmp_path: Path, capsys):
    args = _args(tmp_path, "--dry-run")
    assert main(["--weights", str(tmp_path / "e8.pt"), "--output", str(tmp_path / "out.json"), "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution"]["dry_run"] is True
    assert len(payload["steps"]) == 4
    assert not (tmp_path / "out.json").exists()
