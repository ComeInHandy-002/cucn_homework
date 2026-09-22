"""Application settings loaded from environment variables.

The defaults are intentionally development-friendly: SQLite is used when no
PostgreSQL URL is supplied and inference falls back to a deterministic demo
detector until a local YOLO weight file is configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load the project-local .env before constructing Settings so uvicorn and
# command-line scripts share the same configuration without shell exports.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _choice_env(name: str, default: str, choices: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    return value if value in choices else default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "工业安全智能监测系统")
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./safety_monitor.db")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production-use-at-least-32-bytes")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "720"))
    model_path: str = os.getenv("MODEL_PATH", "models/expanded-ppe-yolov8s-hardcase12.pt")
    model_confidence: float = float(os.getenv("MODEL_CONFIDENCE", "0.25"))
    # Higher inference resolution preserves small PPE boxes in 16:9 video.
    model_image_size: int = max(320, int(os.getenv("MODEL_IMAGE_SIZE", "640")))
    model_device: str = os.getenv("MODEL_DEVICE", "")
    fallback_scenario: str = os.getenv("FALLBACK_SCENARIO", "compliant")
    allow_model_download: bool = _bool_env("ALLOW_MODEL_DOWNLOAD", False)
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))
    result_dir: Path = Path(os.getenv("RESULT_DIR", "results"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "100"))
    # Video jobs use a bounded decode -> inference -> ordered postprocess
    # pipeline.  A small default keeps 8 GB GPUs responsive while allowing
    # batch=16 on larger cards through .env overrides.
    video_batch_size: int = max(1, int(os.getenv("VIDEO_BATCH_SIZE", "8")))
    video_queue_size: int = max(2, int(os.getenv("VIDEO_QUEUE_SIZE", "16")))
    video_decode_backend: str = _choice_env("VIDEO_DECODE_BACKEND", "auto", {"auto", "ffmpeg", "opencv"})
    video_encode_backend: str = _choice_env("VIDEO_ENCODE_BACKEND", "auto", {"auto", "ffmpeg", "opencv"})
    video_half: bool = _bool_env("VIDEO_HALF", True)
    video_tensorrt: bool = _bool_env("VIDEO_TENSORRT", False)
    ffmpeg_binary: str = os.getenv("FFMPEG_BINARY", "ffmpeg")
    ffprobe_binary: str = os.getenv("FFPROBE_BINARY", "ffprobe")
    # ``QUEUE_WORKERS`` remains the requested concurrency.  The service caps
    # it again using MAX_VIDEO_WORKERS and a CUDA free-memory check.
    queue_workers: int = max(1, int(os.getenv("QUEUE_WORKERS", "1")))
    max_video_workers: int = max(1, int(os.getenv("MAX_VIDEO_WORKERS", "1")))
    video_worker_memory_mb: int = max(512, int(os.getenv("VIDEO_WORKER_MEMORY_MB", "3072")))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
