"""FastAPI route contracts for the safety monitoring system."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, require_roles, verify_password
from app.db.database import SessionLocal
from app.config import settings
from app.core.schemas import EventStatus, EventType, JobStatus, SourceType
from app.db.database import get_db
from app.db.models import Camera, DangerZoneRecord, InferenceJobRecord, SafetyEventRecord, User
from app.schemas import (
    CameraCreate,
    CameraResponse,
    DemoAssetResponse,
    EventResponse,
    ExperimentSummaryResponse,
    EventUpdate,
    InferenceResponse,
    JobResponse,
    LoginRequest,
    MetricsResponse,
    TokenResponse,
    ZoneCreate,
    ZoneResponse,
)
from app.services import inference_service


router = APIRouter(prefix="/api/v1", tags=["api"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = PROJECT_ROOT / "data" / "demo" / "selected"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def job_to_response(record: InferenceJobRecord) -> JobResponse:
    return JobResponse(
        job_id=record.id,
        source_type=record.source_type,
        status=record.status,
        progress=record.progress,
        result_path=record.result_path,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def event_to_response(record: SafetyEventRecord) -> EventResponse:
    return EventResponse(
        id=record.id,
        event_type=record.event_type,
        severity=record.severity,
        camera_id=record.camera_id,
        track_id=record.track_id,
        timestamp=record.timestamp,
        evidence_path=record.evidence_path,
        status=record.status,
        zone_id=record.zone_id,
        message=record.message,
        metadata=record.metadata_json or {},
    )


def zone_to_response(record: DangerZoneRecord) -> ZoneResponse:
    return ZoneResponse(
        id=record.id,
        camera_id=record.camera_id,
        name=record.name,
        polygon=record.polygon,
        enabled=record.enabled,
        created_at=record.created_at,
    )


def camera_to_response(record: Camera) -> CameraResponse:
    return CameraResponse(
        id=record.id,
        name=record.name,
        source=record.source,
        location=record.location,
        enabled=record.enabled,
        created_at=record.created_at,
    )


async def save_upload(file: UploadFile, allowed_extensions: set[str]) -> Path:
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file extension: {suffix or 'none'}")
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Uploaded file exceeds size limit")
    path = settings.upload_dir / f"{uuid4().hex}{suffix}"
    path.write_bytes(content)
    return path


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token, expires_in = create_access_token(user.username, {"uid": user.id, "role": user.role})
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@router.post("/inference/images", response_model=InferenceResponse)
async def infer_image(
    file: UploadFile = File(...),
    camera_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InferenceResponse:
    source_path = await save_upload(file, IMAGE_EXTENSIONS)
    result = inference_service.process_image(db, source_path, camera_id=camera_id)
    return InferenceResponse.model_validate(result.model_dump())


@router.post("/inference/videos", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def infer_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    camera_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> JobResponse:
    source_path = await save_upload(file, VIDEO_EXTENSIONS)
    job = inference_service.create_video_job(db, source_path, camera_id=camera_id)
    # The service owns a bounded executor so concurrent requests receive
    # independent model instances only when the configured CUDA memory budget
    # allows it.  The request thread merely enqueues the job.
    background_tasks.add_task(inference_service.enqueue_video_job, job.id)
    return job_to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> JobResponse:
    job = db.get(InferenceJobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_response(job)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    source_type: SourceType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobResponse]:
    query = db.query(InferenceJobRecord)
    if status_filter is not None:
        query = query.filter(InferenceJobRecord.status == status_filter.value)
    if source_type is not None:
        query = query.filter(InferenceJobRecord.source_type == source_type.value)
    records = query.order_by(InferenceJobRecord.created_at.desc()).offset(offset).limit(limit).all()
    return [job_to_response(record) for record in records]


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
    """Return a compact, presentation-friendly summary for a completed job.

    The full frame-by-frame JSON remains available through ``result_path`` for
    debugging and reproducibility, but the workbench should not force a user
    to read that machine-oriented document to understand the outcome.
    """

    job = db.get(InferenceJobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    payload: dict[str, Any] = {
        "job_id": job.id,
        "source_type": job.source_type,
        "status": job.status,
        "progress": job.progress,
        "result_path": job.result_path,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "preview_path": None,
        "frames": 0,
        "detection_count": 0,
        "event_count": 0,
        "detections_by_class": {},
        "events_by_type": {},
        "events": [],
        "metrics": {},
    }
    if not job.result_path:
        return payload
    result_path = Path(job.result_path)
    if not result_path.is_absolute():
        result_path = (PROJECT_ROOT / result_path).resolve()
    result_root = settings.result_dir.resolve()
    try:
        result_path.relative_to(result_root)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid result path")
    if result_path.name != f"{job.id}_result.json" or not result_path.is_file():
        return payload
    result = _read_json(result_path)
    frames = result.get("frames") or []
    detections = result.get("detections") or []
    events = result.get("events") or []
    detections_by_class = Counter(str(item.get("class_name", "unknown")) for item in detections if isinstance(item, dict))
    events_by_type = Counter(str(item.get("event_type", "unknown")) for item in events if isinstance(item, dict))
    preview_path = result.get("preview_path")
    if preview_path:
        preview_file = Path(str(preview_path))
        if not preview_file.is_absolute():
            preview_file = (PROJECT_ROOT / preview_file).resolve()
        # Older jobs were written with an ``mp4v`` preview. If a compatible
        # WebM companion has since been generated, prefer it for browser
        # playback while keeping the original file for audit/download.
        if job.source_type == SourceType.VIDEO.value and preview_file.suffix.lower() == ".mp4":
            webm_file = preview_file.with_suffix(".webm")
            if webm_file.is_file():
                preview_file = webm_file
        try:
            preview_relative = preview_file.relative_to(result_root)
            preview_path = f"results/{preview_relative.as_posix()}" if preview_file.is_file() else None
        except ValueError:
            preview_path = None
    payload.update(
        {
            "preview_path": preview_path,
            "frames": len(frames),
            "detection_count": len(detections),
            "event_count": len(events),
            "detections_by_class": dict(detections_by_class),
            "events_by_type": dict(events_by_type),
            "events": events[:50],
            "metrics": result.get("metrics") or {},
        }
    )
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@router.get("/demo/assets", response_model=list[DemoAssetResponse])
def list_demo_assets(_: User = Depends(get_current_user)) -> list[DemoAssetResponse]:
    """Return only curated files that are present inside the demo asset root."""

    manifest = _read_json(DEMO_DIR / "manifest.json")
    root = DEMO_DIR.resolve()
    assets: list[DemoAssetResponse] = []
    for source_type, entries in ((SourceType.IMAGE.value, manifest.get("images", [])), (SourceType.VIDEO.value, manifest.get("videos", []))):
        for entry in entries:
            relative = str(entry.get("file", "")).replace("\\", "/").lstrip("/")
            if not relative:
                continue
            path = (root / relative).resolve()
            if not path.is_file() or root not in path.parents:
                continue
            assets.append(
                DemoAssetResponse(
                    asset_id=relative,
                    name=path.name,
                    source_type=source_type,
                    url="/demo/" + quote(relative, safe="/"),
                    size=entry.get("size"),
                    duration_seconds=entry.get("duration_seconds"),
                    sha256=entry.get("sha256"),
                )
            )
    return assets


def _experiment_dataset() -> tuple[str, str, list[str], dict[str, Any], str]:
    """Prefer the validated expanded dataset while retaining baseline fallback."""

    merged_validation_path = PROJECT_ROOT / "results" / "expanded_ppe_kaggle_validation_latest.json"
    merged_manifest_path = PROJECT_ROOT / "data" / "expanded_ppe_kaggle" / "dataset_manifest.json"
    merged_validation = _read_json(merged_validation_path)
    merged_manifest = _read_json(merged_manifest_path)
    if merged_validation.get("splits"):
        prepared_at = merged_manifest.get("created_at", "")
        return (
            merged_manifest.get("dataset_name", "Expanded PPE + Kaggle PPE"),
            prepared_at,
            merged_manifest.get("target_classes", ["person", "helmet", "vest"]),
            merged_validation.get("splits", {}),
            "当前展示为 Expanded PPE 与 Kaggle PPE 的图片级去重合并集；共 11,623 张图片、28,853 个标注框。模型指标仅来自实际生成的 test split 评估，不代表未执行的长周期训练。",
        )

    expanded_validation_path = PROJECT_ROOT / "results" / "expanded_ppe_validation.json"
    expanded_sources_path = PROJECT_ROOT / "data" / "expanded_ppe" / "dataset_sources.json"
    expanded_validation = _read_json(expanded_validation_path)
    expanded_sources = _read_json(expanded_sources_path)
    if expanded_validation.get("splits"):
        prepared_at = expanded_sources.get("prepared_at") or expanded_sources.get("created_at") or ""
        return (
            expanded_sources.get("dataset_name", "Expanded PPE"),
            prepared_at,
            expanded_sources.get("target_classes", ["person", "helmet", "vest"]),
            expanded_validation.get("splits", {}),
            "扩充数据已完成质量校验；页面展示 10 epoch GPU test split 实测结果、5 epoch 对照及 1 epoch smoke 链路验证。10 epoch 结果用于当前工程部署，仍不替代计划中的 80 epoch 最终实验。",
        )

    sources = _read_json(PROJECT_ROOT / "data" / "dataset_sources.json")
    validation = _read_json(PROJECT_ROOT / "results" / "dataset_validation.json")
    return (
        sources.get("name", "Construction-PPE"),
        sources.get("downloaded_at", ""),
        sources.get("classes", []),
        validation.get("splits") or sources.get("splits") or {},
        "指标来自项目实际生成的 smoke baseline；不代表正式训练最终精度。",
    )


def _business_per_class(payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Keep the experiment page aligned with the three classes used by rules."""

    aliases = {
        "person": "person",
        "people": "person",
        "worker": "person",
        "helmet": "helmet",
        "hardhat": "helmet",
        "hard_hat": "helmet",
        "safety_helmet": "helmet",
        "vest": "vest",
        "safety_vest": "vest",
        "reflective_vest": "vest",
    }
    filtered: dict[str, dict[str, float]] = {}
    for raw_name, metrics in (payload.get("per_class") or {}).items():
        key = aliases.get(str(raw_name).strip().lower().replace("-", "_").replace(" ", "_"))
        if key and key not in filtered:
            filtered[key] = metrics
    return filtered


@router.get("/experiments/summary", response_model=ExperimentSummaryResponse)
def experiments_summary(_: User = Depends(get_current_user)) -> ExperimentSummaryResponse:
    dataset_name, dataset_version, classes, splits, notes = _experiment_dataset()
    models: list[dict[str, Any]] = []
    current_model_stem = Path(settings.model_path).stem.lower()
    for path, model_name in (
        (settings.result_dir / "baseline-n-smoke-metrics.json", "YOLOv8n"),
        (settings.result_dir / "baseline-s-smoke-metrics.json", "YOLOv8s"),
    ):
        payload = _read_json(path)
        if payload:
            models.append(
                {
                    **payload,
                    "model_name": model_name,
                    "dataset_name": "Construction-PPE 基线（目标三类）",
                    "per_class": _business_per_class(payload),
                }
            )
    for path in sorted(settings.result_dir.glob("expanded-ppe-*-metrics.json")):
        payload = _read_json(path)
        if payload:
            model_name = path.stem.replace("expanded-ppe-", "").replace("-metrics", "")
            if model_name == "yolov8s-smoke":
                model_name = "YOLOv8s (Expanded GPU smoke)"
            elif model_name in {"yolov8s-5ep", "yolov8s-5ep-test"}:
                model_name = "YOLOv8s (Expanded 5 epoch GPU)"
            elif model_name in {"yolov8s-finetune10", "yolov8s-finetune10-test"}:
                model_name = "YOLOv8s (Expanded 10 epoch GPU)"
            elif model_name in {"yolov8s-refine12", "yolov8s-refine12-test"}:
                model_name = "YOLOv8s (Expanded 12 epoch refine)"
            elif model_name in {"yolov8s-kaggle-refine8", "yolov8s-kaggle-refine8-test"}:
                model_name = "YOLOv8s (Expanded + Kaggle 8 epoch refine)"
            elif model_name in {"yolov8s-hardcase12", "yolov8s-hardcase12-test"}:
                model_name = "YOLOv8s (Expanded + Kaggle + hard cases, 12 epoch refine)"
            elif model_name in {"yolov8s-e8-video150", "yolov8s-e8-video150-test"}:
                model_name = "YOLOv8s (E8 video150, 30 epoch candidate)"
            payload_data = str(payload.get("data", "")).replace("\\", "/").lower()
            if "e8-video150" in str(payload.get("weights", "")).lower() or "e8_video150" in payload_data:
                dataset_label = "Expanded PPE + Kaggle PPE + E8 train-only video frames"
            elif "expanded_ppe_hard" in payload_data:
                dataset_label = "Expanded PPE + Kaggle PPE + hard cases"
            elif "expanded_ppe_kaggle" in payload_data:
                dataset_label = "Expanded PPE + Kaggle PPE"
            else:
                dataset_label = "Expanded PPE (Construction-PPE + SH17)"
            models.append(
                {
                    **payload,
                    "model_name": model_name,
                    "dataset_name": dataset_label,
                    "is_current": current_model_stem in path.stem.lower()
                    or current_model_stem in str(payload.get("weights", "")).lower(),
                    "per_class": _business_per_class(payload),
                }
            )
    return ExperimentSummaryResponse(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        classes=classes,
        splits=splits,
        models=models,
        notes=notes,
    )


@router.get("/events", response_model=list[EventResponse])
def list_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status_filter: EventStatus | None = Query(default=None, alias="status"),
    event_type: EventType | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EventResponse]:
    query = db.query(SafetyEventRecord)
    if status_filter is not None:
        query = query.filter(SafetyEventRecord.status == status_filter.value)
    if event_type is not None:
        query = query.filter(SafetyEventRecord.event_type == event_type.value)
    records = query.order_by(SafetyEventRecord.timestamp.desc()).offset(offset).limit(limit).all()
    return [event_to_response(record) for record in records]


@router.patch("/events/{event_id}", response_model=EventResponse)
def update_event(
    event_id: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EventResponse:
    record = db.get(SafetyEventRecord, event_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    record.status = payload.status.value
    db.commit()
    db.refresh(record)
    return event_to_response(record)


@router.post("/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> CameraResponse:
    record = Camera(name=payload.name, source=payload.source, location=payload.location, enabled=payload.enabled)
    db.add(record)
    db.commit()
    db.refresh(record)
    return camera_to_response(record)


@router.get("/cameras", response_model=list[CameraResponse])
def list_cameras(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[CameraResponse]:
    records = db.query(Camera).order_by(Camera.id.asc()).all()
    return [camera_to_response(record) for record in records]


@router.post("/cameras/{camera_id}/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(
    camera_id: int,
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> ZoneResponse:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    polygon = [point.model_dump() for point in payload.polygon]
    record = DangerZoneRecord(camera_id=camera_id, name=payload.name, polygon=polygon, enabled=payload.enabled)
    db.add(record)
    db.commit()
    db.refresh(record)
    return zone_to_response(record)


@router.get("/metrics/summary", response_model=MetricsResponse)
def metrics_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> MetricsResponse:
    events = db.query(SafetyEventRecord).all()
    jobs_today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = db.query(InferenceJobRecord).filter(InferenceJobRecord.created_at >= jobs_today_start).count()
    by_type = Counter(record.event_type for record in events)
    by_severity = Counter(record.severity for record in events)
    return MetricsResponse(
        total_events=len(events),
        open_events=sum(1 for item in events if item.status == EventStatus.OPEN.value),
        acknowledged_events=sum(1 for item in events if item.status == EventStatus.ACKNOWLEDGED.value),
        resolved_events=sum(1 for item in events if item.status == EventStatus.RESOLVED.value),
        events_by_type=dict(by_type),
        events_by_severity=dict(by_severity),
        active_cameras=db.query(Camera).filter(Camera.enabled.is_(True)).count(),
        jobs_today=jobs_today,
    )


@router.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    authorization = websocket.headers.get("authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    db = SessionLocal()
    try:
        if not token:
            await websocket.close(code=1008, reason="Bearer token is required")
            return
        try:
            get_current_user(token, db)
        except HTTPException:
            await websocket.close(code=1008, reason="Invalid or expired access token")
            return
        await websocket.accept()
        await websocket.send_json({"type": "connected", "message": "Safety event websocket is ready"})
        last_timestamp: datetime | None = None
        last_ids: set[str] = set()
        while True:
            query = db.query(SafetyEventRecord).order_by(SafetyEventRecord.timestamp.asc()).limit(200)
            records = query.all()
            for record in records:
                if record.id in last_ids:
                    continue
                if last_timestamp is not None and record.timestamp < last_timestamp:
                    continue
                await websocket.send_json({"type": "event", "event": event_to_response(record).model_dump(mode="json")})
                last_ids.add(record.id)
                last_timestamp = record.timestamp
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except TimeoutError:
                continue
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        return
    finally:
        db.close()


@router.get("/health")
def api_health() -> dict[str, Any]:
    info = inference_service.detector_info()
    return {
        "status": "ok",
        "service": settings.app_name,
        "detector_backend": info["backend"],
        "model_available": info["available"],
        "model_error": info["load_error"],
        **{key: value for key, value in info.items() if key not in {"backend", "available", "load_error"}},
    }
