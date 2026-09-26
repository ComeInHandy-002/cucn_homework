"""Application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.auth import ensure_default_admin
from app.config import settings
from app.db.database import SessionLocal, init_db
from app.schemas import HealthResponse
from app.services import inference_service
from app.services.inference import reset_stale_video_jobs


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SPA_DIST = STATIC_DIR / "dist"
DEMO_DIR = BASE_DIR.parent / "data" / "demo" / "selected"


settings.ensure_directories()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    # Jobs interrupted by a previous process must not stay "running" forever.
    reset_stale_video_jobs()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(settings.result_dir)), name="results")
if DEMO_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(DEMO_DIR)), name="demo")
if (SPA_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(SPA_DIST / "assets")), name="spa-assets")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    info = inference_service.detector_info()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        detector_backend=info["backend"],
        model_available=info["available"],
        model_error=info["load_error"],
        model_path=info.get("model_path"),
        image_size=info.get("image_size"),
        batch_size=info.get("batch_size"),
        half_requested=info.get("half_requested", False),
        half_enabled=info.get("half_enabled", False),
        tensorrt_requested=info.get("tensorrt_requested", False),
        tensorrt_active=info.get("tensorrt_active", False),
        video_decode_backend=info.get("video_decode_backend"),
        video_encode_backend=info.get("video_encode_backend"),
        video_queue_size=info.get("video_queue_size"),
        queue_workers_requested=info.get("queue_workers_requested", 1),
        queue_workers_effective=info.get("queue_workers_effective", 1),
        ffmpeg_available=info.get("ffmpeg_available", False),
        ffmpeg_nvdec=info.get("ffmpeg_nvdec", False),
        ffmpeg_nvenc=info.get("ffmpeg_nvenc", False),
    )


@app.get("/{spa_path:path}", include_in_schema=False)
def spa(spa_path: str = "") -> FileResponse:
    """Serve the Vue3 SPA build, falling back to the legacy workbench.

    API routes and static mounts register before this catch-all, so only
    unmatched paths reach the SPA entry document.
    """

    if (SPA_DIST / "index.html").is_file():
        candidate = (SPA_DIST / spa_path).resolve() if spa_path else None
        if candidate and candidate.is_relative_to(SPA_DIST.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(SPA_DIST / "index.html")
    return FileResponse(STATIC_DIR / "index.html")
