"""Prepare reproducible hard-case samples for PPE fine-tuning.

The three source images are user-provided inspection samples. Their boxes are
kept in source-pixel coordinates here so the provenance and manual decisions
remain reviewable. The generated directory is intentionally separate from
the downloaded datasets and is mounted alongside the normal training split by
``data/expanded_ppe_hard.yaml``.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Box:
    class_id: int
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Case:
    source: str
    boxes: tuple[Box, ...]
    crop: tuple[int, int, int, int] | None = None


# 0=person, 1=helmet, 2=vest. The excavator/signs are deliberately left
# unlabeled as negative background.
CASES = (
    Case(
        source="uploads/adc6cc3e035f4948bf11d0b616bffaca.jpg",
        boxes=(
            Box(0, 403, 148, 587, 666),
            Box(1, 464, 147, 539, 204),
            Box(0, 605, 141, 779, 666),
            Box(1, 653, 144, 726, 202),
            Box(2, 614, 222, 746, 408),
            Box(0, 774, 153, 925, 670),
            Box(1, 800, 154, 875, 210),
            Box(2, 788, 227, 918, 420),
        ),
    ),
    Case(
        source="uploads/45e2ac329e5b480abfc5bec52ca4ca98.jpg",
        boxes=(
            Box(0, 220, 42, 451, 636),
            Box(1, 275, 55, 376, 140),
            Box(2, 266, 145, 410, 385),
            Box(0, 435, 220, 510, 420),
            Box(1, 440, 225, 476, 265),
            Box(2, 438, 245, 503, 351),
        ),
        crop=(140, 0, 540, 640),
    ),
    Case(
        source="uploads/9d806c26de5b4602936b1567cf68469d.jpg",
        boxes=(
            Box(0, 357, 136, 421, 279),
            Box(1, 373, 143, 402, 168),
            Box(2, 364, 163, 408, 218),
        ),
    ),
)


def _clip_box(box: Box, width: int, height: int, crop: tuple[int, int, int, int] | None) -> Box | None:
    offset_x = crop[0] if crop else 0
    offset_y = crop[1] if crop else 0
    max_width = crop[2] - offset_x if crop else width
    max_height = crop[3] - offset_y if crop else height
    x1 = max(0.0, min(float(max_width), box.x1 - offset_x))
    y1 = max(0.0, min(float(max_height), box.y1 - offset_y))
    x2 = max(0.0, min(float(max_width), box.x2 - offset_x))
    y2 = max(0.0, min(float(max_height), box.y2 - offset_y))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return None
    return Box(box.class_id, x1, y1, x2, y2)


def _yolo_lines(boxes: list[Box], width: int, height: int) -> str:
    rows: list[str] = []
    for box in boxes:
        cx = ((box.x1 + box.x2) / 2) / width
        cy = ((box.y1 + box.y2) / 2) / height
        bw = (box.x2 - box.x1) / width
        bh = (box.y2 - box.y1) / height
        rows.append(f"{box.class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return "\n".join(rows) + ("\n" if rows else "")


def _flip_boxes(boxes: list[Box], width: int) -> list[Box]:
    return [Box(item.class_id, width - item.x2, item.y1, width - item.x1, item.y2) for item in boxes]


def _write_sample(image: Image.Image, boxes: list[Box], stem: str, output: Path) -> None:
    image_path = output / "images" / "train" / f"{stem}.jpg"
    label_path = output / "labels" / "train" / f"{stem}.txt"
    image.save(image_path, quality=95, subsampling=0)
    label_path.write_text(_yolo_lines(boxes, image.width, image.height), encoding="utf-8")


def prepare(output: Path, variants: int = 16, seed: int = 20260920) -> dict[str, object]:
    if variants < 1:
        raise ValueError("variants must be at least 1")
    image_dir = output / "images" / "train"
    label_dir = output / "labels" / "train"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    manifest: list[dict[str, object]] = []

    for case_index, case in enumerate(CASES, start=1):
        source_path = ROOT / case.source
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        source = Image.open(source_path).convert("RGB")
        crop = source.crop(case.crop) if case.crop else source
        crop_boxes = [item for item in (_clip_box(box, source.width, source.height, case.crop) for box in case.boxes) if item]
        base = f"hard_{case_index:02d}"
        _write_sample(crop, crop_boxes, base, output)
        manifest.append({"file": f"{base}.jpg", "source": case.source, "variant": "original", "boxes": len(crop_boxes)})

        for variant_index in range(variants):
            image = crop.copy()
            boxes = list(crop_boxes)
            mode = variant_index % 5
            if mode == 0:
                image = ImageEnhance.Brightness(image).enhance(0.72 + 0.08 * (variant_index % 4))
            elif mode == 1:
                image = ImageEnhance.Contrast(image).enhance(0.72 + 0.10 * (variant_index % 4))
            elif mode == 2:
                image = ImageEnhance.Color(image).enhance(0.65 + 0.12 * (variant_index % 4))
            elif mode == 3:
                image = image.filter(ImageFilter.GaussianBlur(radius=0.45 + 0.15 * (variant_index % 3)))
            else:
                image = ImageOps.mirror(image)
                boxes = _flip_boxes(boxes, image.width)
            if variant_index % 3 == 0:
                image = ImageEnhance.Sharpness(image).enhance(0.75 + rng.random() * 0.5)
            stem = f"{base}_aug_{variant_index:02d}"
            _write_sample(image, boxes, stem, output)
            manifest.append({"file": f"{stem}.jpg", "source": case.source, "variant": mode, "boxes": len(boxes)})

    payload = {
        "dataset": "user hard cases",
        "seed": seed,
        "variants_per_case": variants,
        "classes": ["person", "helmet", "vest"],
        "samples": manifest,
    }
    (output / "hard_case_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a reproducible hard-case PPE training split.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "hard_cases")
    parser.add_argument("--variants", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260920)
    args = parser.parse_args()
    payload = prepare(args.output, variants=args.variants, seed=args.seed)
    print(json.dumps({"output": str(args.output), "images": len(payload["samples"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
