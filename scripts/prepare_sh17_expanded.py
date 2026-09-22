"""Download SH17 and build a three-class expanded YOLO dataset.

The original Construction-PPE dataset remains untouched.  This script creates
``data/expanded_ppe`` with both datasets copied into one normalized layout:
0 person, 1 helmet, 2 vest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "downloads" / "sh17"
EXPANDED_DIR = PROJECT_ROOT / "data" / "expanded_ppe"
BASELINE_DIR = PROJECT_ROOT / "data" / "external" / "construction-ppe"
SH17_BASE_URL = "https://huggingface.co/datasets/fathansanum/SH-17-Dataset/resolve/main/SH17-dataset-1"
SPLITS = {"train": "train", "val": "valid", "test": "test"}

# The Roboflow COCO export stores the SH17 names as numeric strings.  The
# original SH17 ordering is documented in its paper and project README.
SH17_CLASS_NAMES = {
    0: "person",
    12: "vest",
    14: "helmet",
}
BASELINE_CLASS_MAP = {0: 1, 2: 2, 6: 0}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def download(url: str, destination: Path, retries: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "safety-monitor-dataset-prep"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            temporary.replace(destination)
            return
        except HTTPError as exc:
            temporary.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            delay = int(exc.headers.get("Retry-After", "5")) if exc.code == 429 else 2**attempt
            time.sleep(min(60, max(1, delay)))
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            time.sleep(min(30, 2**attempt))


def load_coco(split: str) -> dict[str, Any]:
    return json.loads((RAW_DIR / f"{split}_annotations.coco.json").read_text(encoding="utf-8"))


def ensure_annotations() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for output_split, source_split in SPLITS.items():
        url = f"{SH17_BASE_URL}/{source_split}/_annotations.coco.json?download=true"
        download(url, RAW_DIR / f"{output_split}_annotations.coco.json")
    download(f"{SH17_BASE_URL}/README.dataset.txt?download=true", RAW_DIR / "README.dataset.txt")


def normalize_bbox(annotation: dict[str, Any], width: int, height: int) -> tuple[float, float, float, float] | None:
    x, y, box_width, box_height = [float(value) for value in annotation["bbox"]]
    x1 = max(0.0, min(float(width), x))
    y1 = max(0.0, min(float(height), y))
    x2 = max(0.0, min(float(width), x + box_width))
    y2 = max(0.0, min(float(height), y + box_height))
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height, (x2 - x1) / width, (y2 - y1) / height)


def convert_coco_split(split: str, workers: int) -> dict[str, Any]:
    payload = load_coco(split)
    images = {int(item["id"]): item for item in payload["images"]}
    annotations: dict[int, list[dict[str, Any]]] = {image_id: [] for image_id in images}
    for annotation in payload["annotations"]:
        category_id = int(annotation["category_id"]) - 1
        if category_id in SH17_CLASS_NAMES:
            annotations.setdefault(int(annotation["image_id"]), []).append({**annotation, "normalized_class": SH17_CLASS_NAMES[category_id]})

    image_dir = EXPANDED_DIR / "images" / split
    label_dir = EXPANDED_DIR / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, Path]] = []
    for image_id, image in images.items():
        file_name = Path(str(image["file_name"])).name
        target_name = f"sh17_{file_name}"
        destination = image_dir / target_name
        url = f"{SH17_BASE_URL}/{SPLITS[split]}/{file_name}?download=true"
        jobs.append((url, destination))

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download, url, destination) for url, destination in jobs]
        for future in as_completed(futures):
            future.result()
            completed += 1
            if completed % 250 == 0 or completed == len(futures):
                print(f"{split}: downloaded {completed}/{len(futures)}", flush=True)

    valid_images = 0
    mapped_boxes = 0
    for image_id, image in images.items():
        file_name = Path(str(image["file_name"])).name
        target_name = f"sh17_{file_name}"
        label_path = label_dir / f"{Path(target_name).stem}.txt"
        rows: list[str] = []
        for annotation in annotations.get(image_id, []):
            box = normalize_bbox(annotation, int(image["width"]), int(image["height"]))
            if box is None:
                continue
            class_id = {"person": 0, "helmet": 1, "vest": 2}[annotation["normalized_class"]]
            rows.append(f"{class_id} {' '.join(f'{value:.6f}' for value in box)}")
        if rows:
            valid_images += 1
            mapped_boxes += len(rows)
        label_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return {"images": len(images), "images_with_target_labels": valid_images, "mapped_boxes": mapped_boxes}


def copy_baseline() -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for output_split, source_split in (("train", "train"), ("val", "val"), ("test", "test")):
        image_dir = EXPANDED_DIR / "images" / output_split
        label_dir = EXPANDED_DIR / "labels" / output_split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        source_images = [path for path in (BASELINE_DIR / "images" / source_split).iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS]
        mapped = 0
        for source in source_images:
            target_name = f"construction_ppe_{source.name}"
            shutil.copy2(source, image_dir / target_name)
            source_label = BASELINE_DIR / "labels" / source_split / f"{source.stem}.txt"
            rows: list[str] = []
            if source_label.exists():
                for line in source_label.read_text(encoding="utf-8").splitlines():
                    fields = line.split()
                    if len(fields) == 5 and int(fields[0]) in BASELINE_CLASS_MAP:
                        rows.append(f"{BASELINE_CLASS_MAP[int(fields[0])]} {' '.join(fields[1:])}")
            (label_dir / f"{Path(target_name).stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
            mapped += len(rows)
        summary[output_split] = {"images": len(source_images), "mapped_boxes": mapped}
    return summary


def write_yaml() -> Path:
    path = EXPANDED_DIR / "dataset.yaml"
    path.write_text(
        "path: " + EXPANDED_DIR.as_posix() + "\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n  0: person\n  1: helmet\n  2: vest\n",
        encoding="utf-8",
    )
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    ensure_annotations()
    EXPANDED_DIR.mkdir(parents=True, exist_ok=True)
    baseline = copy_baseline()
    sh17 = {split: convert_coco_split(split, max(1, args.workers)) for split in SPLITS}
    yaml_path = write_yaml()
    source_log = {
        "dataset_name": "Expanded PPE (Construction-PPE + SH17)",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "target_classes": ["person", "helmet", "vest"],
        "sources": [
            {
                "name": "Construction-PPE",
                "source_url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip",
                "license": "AGPL-3.0 as distributed with the dataset package",
                "local_data": str(BASELINE_DIR),
                "mapping": {"Person": "person", "helmet": "helmet", "vest": "vest"},
            },
            {
                "name": "SH17",
                "source_url": "https://github.com/ahmadmughees/SH17dataset",
                "paper_dataset_url": "https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection",
                "mirror_url": "https://huggingface.co/datasets/fathansanum/SH-17-Dataset",
                "license": "CC BY-NC-SA 4.0 (SH17 project); mirror README also states CC BY 4.0; verify redistribution terms before publication",
                "mapping": {"Person": "person", "Helmet": "helmet", "Safety-vest": "vest"},
                "raw_annotations": str(RAW_DIR),
                "raw_annotation_sha256": {name: sha256_file(RAW_DIR / f"{name}_annotations.coco.json") for name in SPLITS},
            },
        ],
        "baseline": baseline,
        "sh17": sh17,
        "dataset_yaml": str(yaml_path),
        "notes": "No training metrics are inferred from this preparation step. Re-train and evaluate with scripts/train_yolo.py and scripts/evaluate_yolo.py.",
    }
    (EXPANDED_DIR / "dataset_sources.json").write_text(json.dumps(source_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(source_log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
