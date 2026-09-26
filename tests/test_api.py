from __future__ import annotations


def test_health_and_login(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_image_upload_returns_detections_and_events(client, auth_headers):
    files = {"file": ("demo.jpg", b"not-a-real-image-but-valid-for-fallback", "image/jpeg")}
    response = client.post("/api/v1/inference/images", headers=auth_headers, files=files)
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert payload["detections"]
    assert {event["event_type"] for event in payload["events"]} == {"no_helmet", "no_vest"}

    job = client.get(f"/api/v1/jobs/{payload['job_id']}", headers=auth_headers)
    assert job.status_code == 200
    assert job.json()["status"] == "completed"


def test_job_history_and_experiment_summary(client, auth_headers):
    files = {"file": ("demo.jpg", b"fallback", "image/jpeg")}
    created = client.post("/api/v1/inference/images", headers=auth_headers, files=files)
    assert created.status_code == 200

    jobs = client.get("/api/v1/jobs?source_type=image", headers=auth_headers)
    assert jobs.status_code == 200
    assert jobs.json()[0]["source_type"] == "image"
    assert jobs.json()[0]["status"] == "completed"

    experiments = client.get("/api/v1/experiments/summary", headers=auth_headers)
    assert experiments.status_code == 200
    payload = experiments.json()
    assert payload["dataset_name"] in {
        "Expanded PPE (Construction-PPE + SH17)",
        "Expanded PPE + Kaggle PPE",
    }
    assert {item["model_name"] for item in payload["models"]} >= {"YOLOv8n", "YOLOv8s"}
    assert payload["classes"] == ["person", "helmet", "vest"]
    if payload["dataset_name"] == "Expanded PPE + Kaggle PPE":
        assert payload["splits"]["train"]["images"] == 8276
        assert payload["splits"]["val"]["images"] == 2184
        assert payload["splits"]["test"]["images"] == 1163
    else:
        assert payload["splits"]["train"]["images"] == 6802
        assert payload["splits"]["test"]["images"] == 951
    assert set(payload["models"][1]["per_class"]) == {"person", "helmet", "vest"}
    expanded_models = [item for item in payload["models"] if item["dataset_name"].startswith("Expanded PPE")]
    assert {item["model_name"] for item in expanded_models} >= {
        "YOLOv8s (Expanded GPU smoke)",
        "YOLOv8s (Expanded 5 epoch GPU)",
    }
    assert all(set(item["per_class"]) == {"person", "helmet", "vest"} for item in expanded_models)
    current_models = [item for item in payload["models"] if item["is_current"]]
    assert len(current_models) <= 1
    if current_models:
        assert "hard cases" in current_models[0]["model_name"]
    # The merged-data summary now leads with the real test split and keeps the
    # long-training boundary explicit; the legacy branch mentions smoke/5 ep.
    assert ("test split" in payload["notes"]) or ("smoke" in payload["notes"])
    assert ("长周期训练" in payload["notes"]) or ("5 epoch" in payload["notes"])


def test_job_result_summary_prefers_media_over_raw_json(client, auth_headers):
    files = {"file": ("demo.jpg", b"fallback", "image/jpeg")}
    created = client.post("/api/v1/inference/images", headers=auth_headers, files=files)
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    result = client.get(f"/api/v1/jobs/{job_id}/result", headers=auth_headers)
    assert result.status_code == 200
    payload = result.json()
    assert payload["job_id"] == job_id
    assert payload["source_type"] == "image"
    assert payload["frames"] == 1
    assert payload["detection_count"] >= 1
    assert payload["preview_path"].startswith("results/")
    assert payload["result_path"].endswith("_result.json")
    assert set(payload["events_by_type"]) == {"no_helmet", "no_vest"}


def test_demo_assets_are_curated_and_served(client, auth_headers):
    response = client.get("/api/v1/demo/assets", headers=auth_headers)
    assert response.status_code == 200
    assets = response.json()
    assert len(assets) >= 2
    assert {asset["source_type"] for asset in assets} == {"image", "video"}
    image = next(asset for asset in assets if asset["source_type"] == "image")
    video = next(asset for asset in assets if asset["source_type"] == "video")
    assert image["url"].startswith("/demo/images/")
    assert video["url"].startswith("/demo/videos/")
    assert client.get(image["url"]).status_code == 200
    assert client.get(video["url"]).status_code == 200


def test_events_can_be_queried_and_updated(client, auth_headers):
    files = {"file": ("demo.jpg", b"fallback", "image/jpeg")}
    client.post("/api/v1/inference/images", headers=auth_headers, files=files)

    events = client.get("/api/v1/events", headers=auth_headers)
    assert events.status_code == 200
    event_id = events.json()[0]["id"]

    updated = client.patch(f"/api/v1/events/{event_id}", headers=auth_headers, json={"status": "acknowledged"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "acknowledged"


def test_camera_zone_and_metrics(client, auth_headers):
    camera = client.post("/api/v1/cameras", headers=auth_headers, json={"name": "车间A", "source": "local"})
    assert camera.status_code == 201
    camera_id = camera.json()["id"]

    zone = client.post(
        f"/api/v1/cameras/{camera_id}/zones",
        headers=auth_headers,
        json={
            "name": "切割区",
            "polygon": [{"x": 150, "y": 250}, {"x": 500, "y": 250}, {"x": 500, "y": 470}, {"x": 150, "y": 470}],
        },
    )
    assert zone.status_code == 201

    cameras = client.get("/api/v1/cameras", headers=auth_headers)
    assert cameras.status_code == 200
    assert len(cameras.json()) == 1

    metrics = client.get("/api/v1/metrics/summary", headers=auth_headers)
    assert metrics.status_code == 200
    assert metrics.json()["active_cameras"] == 1


def test_websocket_requires_token_and_streams_existing_events(client, auth_headers):
    files = {"file": ("demo.jpg", b"fallback", "image/jpeg")}
    client.post("/api/v1/inference/images", headers=auth_headers, files=files)
    token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws/events?token={token}") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        message = websocket.receive_json()
        assert message["type"] == "event"
        assert message["event"]["event_type"] in {"no_helmet", "no_vest"}


def test_api_rejects_unauthorized_and_invalid_inputs(client, auth_headers):
    assert client.get("/api/v1/events").status_code == 401
    assert client.get("/api/v1/jobs/not-found", headers=auth_headers).status_code == 404
    assert client.patch(
        "/api/v1/events/not-found", headers=auth_headers, json={"status": "resolved"}
    ).status_code == 404
    assert client.post(
        "/api/v1/inference/images",
        headers=auth_headers,
        files={"file": ("payload.txt", b"not an image", "text/plain")},
    ).status_code == 400
    assert client.post(
        "/api/v1/inference/videos",
        headers=auth_headers,
        files={"file": ("payload.txt", b"not a video", "text/plain")},
    ).status_code == 400
    assert client.post(
        "/api/v1/cameras/999999/zones",
        headers=auth_headers,
        json={"name": "zone", "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]},
    ).status_code == 404


def test_frontend_static_content_types(client):
    assert client.get("/static/index.html").headers["content-type"].startswith("text/html")
    assert client.get("/static/styles.css").headers["content-type"].startswith("text/css")
    assert client.get("/static/app.js").headers["content-type"].startswith("text/javascript")


def test_event_and_job_timestamps_are_serialized_as_utc(client, auth_headers):
    """Naive SQLite rows must come back with a UTC marker, not bare wall time."""

    files = {"file": ("demo.jpg", b"fallback", "image/jpeg")}
    created = client.post("/api/v1/inference/images", headers=auth_headers, files=files)
    assert created.status_code == 200

    events = client.get("/api/v1/events", headers=auth_headers).json()
    assert events
    assert events[0]["timestamp"].endswith(("Z", "+00:00"))

    jobs = client.get("/api/v1/jobs", headers=auth_headers).json()
    assert jobs
    assert jobs[0]["created_at"].endswith(("Z", "+00:00"))


def test_relative_zone_triggers_intrusion_on_fallback_frame(client, auth_headers):
    """A 0-1 zone must fire regardless of the frame resolution it is checked against."""

    camera = client.post("/api/v1/cameras", headers=auth_headers, json={"name": "炉区", "source": "local"})
    camera_id = camera.json()["id"]
    zone = client.post(
        f"/api/v1/cameras/{camera_id}/zones",
        headers=auth_headers,
        json={
            "name": "熔炉区",
            "coordinate_space": "relative",
            "polygon": [{"x": 0.3, "y": 0.8}, {"x": 0.7, "y": 0.8}, {"x": 0.7, "y": 1.0}, {"x": 0.3, "y": 1.0}],
        },
    )
    assert zone.status_code == 201

    response = client.post(
        "/api/v1/inference/images",
        headers=auth_headers,
        files={"file": ("worker.jpg", b"fallback", "image/jpeg")},
        data={"camera_id": str(camera_id)},
    )
    assert response.status_code == 200
    intrusion = [event for event in response.json()["events"] if event["event_type"] == "intrusion"]
    assert intrusion and intrusion[0]["zone_id"] == str(zone.json()["id"])


def test_zones_can_be_listed_deleted_and_validated(client, auth_headers):
    camera = client.post("/api/v1/cameras", headers=auth_headers, json={"name": "车间B", "source": "local"})
    camera_id = camera.json()["id"]
    zone = client.post(
        f"/api/v1/cameras/{camera_id}/zones",
        headers=auth_headers,
        json={
            "name": "切割区",
            "coordinate_space": "relative",
            "polygon": [{"x": 0.2, "y": 0.5}, {"x": 0.8, "y": 0.5}, {"x": 0.8, "y": 0.95}],
        },
    )
    assert zone.status_code == 201
    zone_id = zone.json()["id"]
    assert zone.json()["coordinate_space"] == "relative"

    assert client.post(
        f"/api/v1/cameras/{camera_id}/zones",
        headers=auth_headers,
        json={
            "name": "越界区域",
            "coordinate_space": "relative",
            "polygon": [{"x": 150, "y": 0.5}, {"x": 300, "y": 0.5}, {"x": 300, "y": 0.9}],
        },
    ).status_code == 422

    zones = client.get("/api/v1/zones", headers=auth_headers)
    assert zones.status_code == 200
    assert [item["id"] for item in zones.json()] == [zone_id]

    assert client.delete(f"/api/v1/zones/{zone_id}", headers=auth_headers).status_code == 204
    assert client.get("/api/v1/zones", headers=auth_headers).json() == []
    assert client.delete(f"/api/v1/zones/{zone_id}", headers=auth_headers).status_code == 404


def test_websocket_streams_newest_events_beyond_200_history(client, auth_headers):
    from datetime import datetime, timedelta, timezone

    from app.db.database import SessionLocal
    from app.db.models import SafetyEventRecord

    db = SessionLocal()
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    newest_id = ""
    for index in range(250):
        record = SafetyEventRecord(
            event_type="no_helmet",
            severity="high",
            timestamp=base + timedelta(seconds=index),
            status="open",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        newest_id = record.id
    db.close()

    token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws/events?token={token}") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        found_newest = False
        for _ in range(200):
            message = websocket.receive_json()
            if message["type"] == "event" and message["event"]["id"] == newest_id:
                found_newest = True
                break
        assert found_newest, "the newest event must be streamed even with 250 stored events"


def test_service_restart_marks_stale_jobs_failed(client, auth_headers):
    from app.db.database import SessionLocal
    from app.db.models import InferenceJobRecord
    from app.services.inference import reset_stale_video_jobs

    db = SessionLocal()
    job = InferenceJobRecord(source_type="video", status="running")
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    assert reset_stale_video_jobs() == 1

    db = SessionLocal()
    refreshed = db.get(InferenceJobRecord, job_id)
    assert refreshed.status == "failed"
    assert refreshed.error_message
    db.close()
