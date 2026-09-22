"""Report runtime dependencies and optional GPU/model availability."""

from __future__ import annotations

import importlib.util
import json
import platform
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "sqlalchemy": "sqlalchemy",
    "pydantic": "pydantic",
    "multipart": "python-multipart",
    "jwt": "PyJWT",
    "PIL": "Pillow",
    "numpy": "numpy",
    "cv2": "opencv-python",
    "ultralytics": "ultralytics",
    "torch": "torch",
    "psycopg": "psycopg",
}


def main() -> int:
    modules = {module: importlib.util.find_spec(module) is not None for module in REQUIRED_MODULES}
    report: dict[str, object] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "python_supported": (sys.version_info.major, sys.version_info.minor) == (3, 12),
        "modules": modules,
        "missing_packages": [package for module, package in REQUIRED_MODULES.items() if not modules[module]],
        "model_weights": (PROJECT_ROOT / "models" / "yolov8s.pt").exists(),
    }
    try:
        import torch

        report["torch"] = torch.__version__
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["cuda_version"] = torch.version.cuda
        report["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as exc:  # pragma: no cover - diagnostic fallback
        report["torch_error"] = str(exc)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["python_supported"] and not report["missing_packages"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
