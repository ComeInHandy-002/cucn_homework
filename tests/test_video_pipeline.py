"""End-to-end video pipeline regression in fallback mode (no weights, no GPU).

The three-thread decode -> batch inference -> ordered postprocess pipeline in
``app.services.inference`` previously had no automated coverage; these tests
exercise it on a synthetic video through the real job lifecycle.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import InferenceJobRecord, SafetyEventRecord
from app.services import inference_service


@pytest.fixture()
def isolated_video_settings(tmp_path, monkeypatch):
    replaced = dataclasses.replace(
        settings,
        result_dir=tmp_path,
        video_batch_size=4,
        video_queue_size=4,
    )
    monkeypatch.setattr("app.services.inference.settings", replaced)
    return replaced


def _write_synthetic_video(path: Path, frames: int = 30, width: int = 64, height: int = 48) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (width, height))
    assert writer.isOpened(), "OpenCV writer failed to open; cannot build the pipeline fixture"
    for index in range(frames):
        value = 30 + (index * 7) % 200
        writer.write(np.full((height, width, 3), value, dtype=np.uint8))
    writer.release()


def test_fallback_pipeline_completes_in_order_and_persists_events(isolated_video_settings, tmp_path):
    video_path = tmp_path / "clip.mp4"
    _write_synthetic_video(video_path)

    db = SessionLocal()
    job = InferenceJobRecord(source_type="video", source_path=str(video_path), status="queued")
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    inference_service.run_video_job(job_id)

    db = SessionLocal()
    job = db.get(InferenceJobRecord, job_id)
    assert job is not None
    assert job.status == "completed", job.error_message
    assert job.progress == 100.0
    payload = json.loads(Path(job.result_path).read_text(encoding="utf-8"))

    # The ordered worker must hand the tracker strict frame order.
    assert [frame["frame_index"] for frame in payload["frames"]] == list(range(30))
    assert payload["metrics"]["decoded_frames"] == 30
    assert payload["metrics"]["total_fps"] > 0

    # FALLBACK_SCENARIO=no_ppe emits one person per frame.  The tracker hides
    # the person for 3 frames and the rule engine applies a 15-observation PPE
    # warmup, so 30 frames are needed before both alerts can be confirmed.
    event_types = {event["event_type"] for event in payload["events"]}
    assert {"no_helmet", "no_vest"} <= event_types
    for event in payload["events"]:
        assert event["evidence_path"]
        assert Path(event["evidence_path"]).is_file()
    assert Path(payload["preview_path"]).is_file()

    persisted = db.query(SafetyEventRecord).count()
    db.close()
    assert persisted == len(payload["events"])
