from __future__ import annotations

import os
from pathlib import Path


os.environ.setdefault("FALLBACK_SCENARIO", "no_ppe")

from app.auth import ensure_default_admin
from app.db.database import SessionLocal, init_db
from app.services import inference_service


def make_demo_image(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (640, 480), "#f3f4f6")
        draw = ImageDraw.Draw(image)
        draw.rectangle((190, 60, 450, 440), outline="#64748b", width=4)
        draw.text((24, 24), "fallback demo frame", fill="#111827")
        image.save(path)
    except Exception:
        path.write_bytes(b"fallback demo frame")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        input_path = Path("uploads/demo_input.jpg")
        input_path.parent.mkdir(parents=True, exist_ok=True)
        make_demo_image(input_path)
        result = inference_service.process_image(db, input_path)
        print(result.model_dump_json(indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
