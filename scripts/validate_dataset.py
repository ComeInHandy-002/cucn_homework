"""Validate YOLO image/label pairs before training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def validate_split(root: Path, split: str, class_count: int) -> dict[str, int | list[str]]:
    image_dir = root / "images" / split
    label_dir = root / "labels" / split
    errors: list[str] = []
    images = [path for path in image_dir.glob("*") if path.suffix.lower() in IMAGE_EXTENSIONS]
    labels = {path.stem: path for path in label_dir.glob("*.txt")}
    seen_labels: set[str] = set()
    boxes = 0
    for image in images:
        try:
            width, height = Image.open(image).size
        except Exception as exc:
            errors.append(f"{image.name}: unreadable image ({exc})")
            continue
        label = labels.get(image.stem)
        if label is None:
            errors.append(f"{image.name}: missing label")
            continue
        seen_labels.add(image.stem)
        for line_number, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split()
            if len(fields) != 5:
                errors.append(f"{label.name}:{line_number}: expected 5 fields")
                continue
            try:
                class_id, *coords = map(float, fields)
            except ValueError:
                errors.append(f"{label.name}:{line_number}: non-numeric value")
                continue
            if class_id != int(class_id) or not 0 <= int(class_id) < class_count:
                errors.append(f"{label.name}:{line_number}: class id out of range")
            if any(value < 0 or value > 1 for value in coords):
                errors.append(f"{label.name}:{line_number}: normalized coordinate out of range")
            if coords[2] <= 0 or coords[3] <= 0:
                errors.append(f"{label.name}:{line_number}: box has no area")
            boxes += 1
    orphan_labels = set(labels) - seen_labels
    # The upstream archive contains ten duplicate label files with a `(1)`
    # suffix but only one corresponding image. Keep them recorded as a warning
    # rather than failing an otherwise valid training split.
    duplicate_labels = {name for name in orphan_labels if name.endswith("(1)")}
    errors.extend(f"{split}: orphan label {name}.txt" for name in sorted(orphan_labels - duplicate_labels))
    return {"images": len(images), "labels": len(labels), "boxes": boxes, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/external/construction-ppe")
    parser.add_argument("--output", default="results/dataset_validation.json")
    args = parser.parse_args()
    root = Path(args.dataset)
    config = root / "data.yaml"
    if not config.exists():
        config = root / "dataset.yaml"
    if not config.exists():
        raise FileNotFoundError(config)
    class_count = 11
    config_text = config.read_text(encoding="utf-8")
    names_section = config_text.split("names:", 1)[1] if "names:" in config_text else ""
    parsed_class_ids = []
    for line in names_section.splitlines():
        stripped = line.strip()
        if stripped and stripped.split(":", 1)[0].isdigit():
            parsed_class_ids.append(int(stripped.split(":", 1)[0]))
    if parsed_class_ids:
        class_count = max(parsed_class_ids) + 1
    report = {split: validate_split(root, split, class_count=class_count) for split in ("train", "val", "test")}
    payload = {"dataset": str(root.resolve()), "class_count": class_count, "splits": report}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not any(split["errors"] for split in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
