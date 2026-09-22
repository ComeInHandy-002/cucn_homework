"""Build the E8 PPE fine-tuning split from licensed videos and train-only hard cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CLASS_NAMES = {0: "person", 1: "helmet", 2: "vest"}
COLORS = {0: (50, 190, 255), 1: (40, 220, 80), 2: (230, 160, 40)}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class VideoSpec:
    file: str
    source_group: str
    role: str
    interval_seconds: float
    max_frames: int
    person_confidence: float = 0.25
    min_helmet_coverage: float = 0.0
    min_vest_coverage: float = 0.0


@dataclass(frozen=True)
class Box:
    class_id: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


VIDEO_SPECS = (
    VideoSpec(
        file="nasa_artemis_iii_ksc_ppe.webm",
        source_group="nasa-ksc-artemis-iii-2026",
        role="pseudo_positive",
        interval_seconds=1.0,
        max_frames=140,
        person_confidence=0.25,
        min_helmet_coverage=0.65,
        min_vest_coverage=0.65,
    ),
    VideoSpec(
        file="japan_road_jackhammer.webm",
        source_group="nesnad-japan-jackhammer",
        role="pseudo_positive",
        interval_seconds=0.4,
        max_frames=25,
        person_confidence=0.22,
        min_helmet_coverage=0.65,
        min_vest_coverage=0.50,
    ),
    VideoSpec(
        file="moira_construction_2025_13.webm",
        source_group="acabashi-moira-close-2025",
        role="pseudo_positive",
        interval_seconds=2.5,
        max_frames=140,
        person_confidence=0.18,
        min_helmet_coverage=0.20,
        min_vest_coverage=0.20,
    ),
    VideoSpec(
        file="cerro_armazones_heavy_machinery.webm",
        source_group="eso-cerro-armazones",
        role="hard_negative",
        interval_seconds=2.0,
        max_frames=40,
    ),
    VideoSpec(
        file="moira_excavator_2025_01.webm",
        source_group="acabashi-moira-close-2025",
        role="hard_negative",
        interval_seconds=0.8,
        max_frames=35,
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(frame: np.ndarray) -> int:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def yolo_text(boxes: Iterable[Box], width: int, height: int) -> str:
    rows: list[str] = []
    for box in boxes:
        cx = ((box.x1 + box.x2) / 2.0) / width
        cy = ((box.y1 + box.y2) / 2.0) / height
        bw = (box.x2 - box.x1) / width
        bh = (box.y2 - box.y1) / height
        rows.append(f"{box.class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return "\n".join(rows) + ("\n" if rows else "")


def parse_yolo_label(path: Path, width: int, height: int) -> list[Box]:
    boxes: list[Box] = []
    if not path.exists():
        return boxes
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.split()
        if len(parts) != 5:
            continue
        class_id = int(float(parts[0]))
        cx, cy, bw, bh = (float(value) for value in parts[1:])
        boxes.append(
            Box(
                class_id=class_id,
                confidence=1.0,
                x1=(cx - bw / 2.0) * width,
                y1=(cy - bh / 2.0) * height,
                x2=(cx + bw / 2.0) * width,
                y2=(cy + bh / 2.0) * height,
            )
        )
    return boxes


def associated(ppe: Box, person: Box) -> bool:
    width = person.x2 - person.x1
    height = person.y2 - person.y1
    center_x = (ppe.x1 + ppe.x2) / 2.0
    center_y = (ppe.y1 + ppe.y2) / 2.0
    if not (person.x1 - width * 0.12 <= center_x <= person.x2 + width * 0.12):
        return False
    if ppe.class_id == 1:
        return person.y1 - height * 0.12 <= center_y <= person.y1 + height * 0.45
    return person.y1 + height * 0.05 <= center_y <= person.y1 + height * 0.82


def filter_prediction(result: object, spec: VideoSpec) -> tuple[list[Box], dict[str, float]] | None:
    raw: list[Box] = []
    if result.boxes is not None and len(result.boxes):
        xyxy = result.boxes.xyxy.detach().cpu().numpy()
        confidence = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        for coords, score, class_id in zip(xyxy, confidence, classes):
            threshold = spec.person_confidence if class_id == 0 else (0.10 if class_id == 1 else 0.14)
            if class_id in CLASS_NAMES and float(score) >= threshold:
                raw.append(Box(int(class_id), float(score), *[float(item) for item in coords]))

    people = [item for item in raw if item.class_id == 0]
    if not people:
        return None
    ppe = [item for item in raw if item.class_id in {1, 2} and any(associated(item, person) for person in people)]
    helmet_covered = sum(any(item.class_id == 1 and associated(item, person) for item in ppe) for person in people)
    vest_covered = sum(any(item.class_id == 2 and associated(item, person) for item in ppe) for person in people)
    helmet_coverage = helmet_covered / len(people)
    vest_coverage = vest_covered / len(people)
    if helmet_coverage < spec.min_helmet_coverage or vest_coverage < spec.min_vest_coverage:
        return None
    boxes = sorted(people + ppe, key=lambda item: (item.class_id, item.x1, item.y1))
    return boxes, {"helmet_coverage": helmet_coverage, "vest_coverage": vest_coverage}


def candidate_frames(video_path: Path, spec: VideoSpec) -> list[tuple[int, np.ndarray, float, int]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0.0
    timestamps = np.arange(1.0, max(1.0, duration - 1.0), spec.interval_seconds)
    hashes: list[int] = []
    selected: list[tuple[int, np.ndarray, float, int]] = []
    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp * 1000.0))
        ok, frame = capture.read()
        if not ok or frame is None or frame.size == 0:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < 28.0 or float(gray.mean()) < 12.0:
            continue
        fingerprint = dhash(frame)
        if hashes and min(hamming(fingerprint, previous) for previous in hashes[-30:]) < 3:
            continue
        hashes.append(fingerprint)
        selected.append((int(round(timestamp * 1000.0)), frame, blur_score, fingerprint))
        if len(selected) >= spec.max_frames:
            break
    capture.release()
    return selected


def save_frame(
    frame: np.ndarray,
    boxes: list[Box],
    stem: str,
    image_dir: Path,
    label_dir: Path,
) -> tuple[Path, Path]:
    image_path = image_dir / f"{stem}.jpg"
    label_path = label_dir / f"{stem}.txt"
    if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise RuntimeError(f"Failed to write image: {image_path}")
    label_path.write_text(yolo_text(boxes, frame.shape[1], frame.shape[0]), encoding="utf-8")
    return image_path, label_path


def draw_boxes(frame: np.ndarray, boxes: list[Box], title: str) -> np.ndarray:
    canvas = frame.copy()
    for box in boxes:
        color = COLORS[box.class_id]
        start = (int(round(box.x1)), int(round(box.y1)))
        end = (int(round(box.x2)), int(round(box.y2)))
        cv2.rectangle(canvas, start, end, color, 2)
        label = f"{CLASS_NAMES[box.class_id]} {box.confidence:.2f}"
        cv2.putText(canvas, label, (start[0], max(16, start[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 30), (20, 20, 20), -1)
    cv2.putText(canvas, title[:80], (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def write_review_sheets(records: list[dict[str, object]], review_dir: Path, prefix: str) -> list[str]:
    if not records:
        return []
    outputs: list[str] = []
    for page_index in range(0, len(records), 20):
        page = records[page_index : page_index + 20]
        cells: list[np.ndarray] = []
        for record in page:
            frame = cv2.imread(str(record["image_path"]))
            boxes = [Box(**item) for item in record["boxes"]]
            annotated = draw_boxes(frame, boxes, str(record["review_title"]))
            target_width, target_height = 320, 200
            scale = min(target_width / annotated.shape[1], (target_height - 22) / annotated.shape[0])
            resized = cv2.resize(
                annotated,
                (max(1, int(annotated.shape[1] * scale)), max(1, int(annotated.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
            cell = np.full((target_height, target_width, 3), 24, dtype=np.uint8)
            x = (target_width - resized.shape[1]) // 2
            y = 22 + (target_height - 22 - resized.shape[0]) // 2
            cell[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
            cv2.putText(cell, str(record["review_title"])[:48], (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)
            cells.append(cell)
        blank = np.full((200, 320, 3), 24, dtype=np.uint8)
        cells.extend([blank] * (20 - len(cells)))
        sheet = np.vstack([np.hstack(cells[row * 5 : (row + 1) * 5]) for row in range(4)])
        target = review_dir / f"{prefix}_{page_index // 20 + 1:02d}.jpg"
        cv2.imwrite(str(target), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
        outputs.append(str(target.relative_to(review_dir.parent)).replace("\\", "/"))
    return outputs


def process_videos(
    model: object,
    videos_dir: Path,
    image_dir: Path,
    label_dir: Path,
    review_dir: Path,
    inference_size: int,
    device: str,
) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    all_records: list[dict[str, object]] = []
    sheets: dict[str, list[str]] = {}
    for spec in VIDEO_SPECS:
        video_path = videos_dir / spec.file
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        candidates = candidate_frames(video_path, spec)
        records: list[dict[str, object]] = []
        if spec.role == "hard_negative":
            selected = []
            for start in range(0, len(candidates), 8):
                batch = candidates[start : start + 8]
                results = model.predict(
                    source=[item[1] for item in batch],
                    imgsz=inference_size,
                    conf=0.12,
                    iou=0.55,
                    classes=[0],
                    device=device,
                    augment=False,
                    max_det=50,
                    verbose=False,
                )
                for candidate, result in zip(batch, results):
                    person_scores = []
                    if result.boxes is not None and len(result.boxes):
                        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
                        scores = result.boxes.conf.detach().cpu().numpy()
                        person_scores = [float(score) for class_id, score in zip(classes, scores) if int(class_id) == 0]
                    # A hard-negative frame must not contain a model-visible person.
                    # This prevents visible workers in machinery footage becoming empty labels.
                    if not person_scores:
                        selected.append((*candidate, [], {}))
        else:
            selected = []
            for start in range(0, len(candidates), 2):
                batch = candidates[start : start + 2]
                results = model.predict(
                    source=[item[1] for item in batch],
                    imgsz=inference_size,
                    conf=0.03,
                    iou=0.55,
                    classes=[0, 1, 2],
                    device=device,
                    augment=False,
                    max_det=100,
                    verbose=False,
                )
                for candidate, result in zip(batch, results):
                    filtered = filter_prediction(result, spec)
                    if filtered is None:
                        continue
                    boxes, coverage = filtered
                    selected.append((*candidate, boxes, coverage))

        slug = Path(spec.file).stem.replace("-", "_")[:42]
        for timestamp, frame, blur_score, fingerprint, boxes, coverage in selected:
            stem = f"video_{slug}_{timestamp:09d}"
            image_path, label_path = save_frame(frame, boxes, stem, image_dir, label_dir)
            class_counts = {name: sum(item.class_id == class_id for item in boxes) for class_id, name in CLASS_NAMES.items()}
            record = {
                "kind": spec.role,
                "file": image_path.name,
                "image_path": image_path,
                "label_path": label_path,
                "source_video": spec.file,
                "source_group": spec.source_group,
                "timestamp_ms": timestamp,
                "blur_score": round(blur_score, 3),
                "dhash": f"{fingerprint:016x}",
                "boxes": [asdict(item) for item in boxes],
                "class_counts": class_counts,
                "coverage": coverage,
                "review_title": f"{spec.source_group} {timestamp / 1000.0:.1f}s",
            }
            records.append(record)
            all_records.append(record)
        sheets[spec.source_group + "-" + spec.role] = write_review_sheets(records, review_dir, slug)
        print(json.dumps({"source": spec.file, "candidates": len(candidates), "accepted": len(records), "role": spec.role}))
    return all_records, sheets


def find_image(images_by_stem: dict[str, Path], label_path: Path) -> Path | None:
    return images_by_stem.get(label_path.stem)


def mine_train_helmets(
    base_root: Path,
    image_dir: Path,
    label_dir: Path,
    review_dir: Path,
    dark_limit: int,
    small_limit: int,
) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    train_images = base_root / "images" / "train"
    train_labels = base_root / "labels" / "train"
    images_by_stem = {item.stem: item for item in train_images.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES}
    candidates: list[dict[str, object]] = []
    for label_path in sorted(train_labels.glob("*.txt")):
        source_image = find_image(images_by_stem, label_path)
        if source_image is None:
            continue
        raw = cv2.imread(str(source_image))
        if raw is None:
            continue
        height, width = raw.shape[:2]
        boxes = parse_yolo_label(label_path, width, height)
        helmets = [item for item in boxes if item.class_id == 1]
        if not helmets:
            continue
        gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        darkness: list[float] = []
        area_ratios: list[float] = []
        for helmet in helmets:
            x1 = max(0, min(width - 1, int(round(helmet.x1))))
            y1 = max(0, min(height - 1, int(round(helmet.y1))))
            x2 = max(x1 + 1, min(width, int(round(helmet.x2))))
            y2 = max(y1 + 1, min(height, int(round(helmet.y2))))
            crop = gray[y1:y2, x1:x2]
            if crop.size:
                inner = crop[crop.shape[0] // 6 : max(crop.shape[0] // 6 + 1, crop.shape[0] * 5 // 6), crop.shape[1] // 6 : max(crop.shape[1] // 6 + 1, crop.shape[1] * 5 // 6)]
                darkness.append(float(np.median(inner if inner.size else crop)))
                area_ratios.append(((x2 - x1) * (y2 - y1)) / float(width * height))
        if darkness:
            candidates.append(
                {
                    "source_image": source_image,
                    "source_label": label_path,
                    "boxes": boxes,
                    "darkness": min(darkness),
                    "smallest_area_ratio": min(area_ratios),
                }
            )

    dark = [item for item in sorted(candidates, key=lambda item: item["darkness"]) if item["darkness"] <= 105.0][:dark_limit]
    dark_sources = {str(item["source_image"]) for item in dark}
    small = [
        item
        for item in sorted(candidates, key=lambda item: item["smallest_area_ratio"])
        if str(item["source_image"]) not in dark_sources and item["smallest_area_ratio"] <= 0.006
    ][:small_limit]

    records: list[dict[str, object]] = []
    groups = (("mined_dark", dark), ("mined_small", small))
    sheets: dict[str, list[str]] = {}
    for criterion, selected in groups:
        criterion_records: list[dict[str, object]] = []
        for index, item in enumerate(selected, start=1):
            source_image = item["source_image"]
            source_label = item["source_label"]
            stem = f"{criterion}_{index:03d}_{source_image.stem[:48]}"
            destination_image = image_dir / f"{stem}{source_image.suffix.lower()}"
            destination_label = label_dir / f"{stem}.txt"
            shutil.copy2(source_image, destination_image)
            shutil.copy2(source_label, destination_label)
            record = {
                "kind": criterion,
                "file": destination_image.name,
                "image_path": destination_image,
                "label_path": destination_label,
                "source_image": str(source_image.relative_to(ROOT)).replace("\\", "/"),
                "source_group": "expanded-ppe-kaggle-train",
                "darkness": round(float(item["darkness"]), 3),
                "smallest_area_ratio": round(float(item["smallest_area_ratio"]), 8),
                "boxes": [asdict(box) for box in item["boxes"]],
                "class_counts": {name: sum(box.class_id == class_id for box in item["boxes"]) for class_id, name in CLASS_NAMES.items()},
                "review_title": f"{criterion} {source_image.name}",
            }
            records.append(record)
            criterion_records.append(record)
        sheets[criterion] = write_review_sheets(criterion_records, review_dir, criterion)
    print(json.dumps({"mined_dark": len(dark), "mined_small": len(small)}))
    return records, sheets


def manifest_record(record: dict[str, object], output: Path) -> dict[str, object]:
    image_path = record["image_path"]
    label_path = record["label_path"]
    payload = {key: value for key, value in record.items() if key not in {"image_path", "label_path", "boxes", "review_title"}}
    payload["image"] = str(image_path.relative_to(output)).replace("\\", "/")
    payload["label"] = str(label_path.relative_to(output)).replace("\\", "/")
    payload["image_sha256"] = sha256_file(image_path)
    payload["label_sha256"] = sha256_file(label_path)
    return payload


def write_dataset_yaml(target: Path, base_root: Path, output: Path) -> None:
    base_root = base_root.resolve()
    output = output.resolve()
    relative_output = output.relative_to(base_root.parent).as_posix()
    text = "\n".join(
        [
            f"path: {base_root.as_posix()}",
            "train:",
            "  - images/train",
            "  - ../hard_cases/images/train",
            f"  - ../{relative_output}/images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: person",
            "  1: helmet",
            "  2: vest",
            "",
        ]
    )
    target.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare E8 video and helmet hard-case training data.")
    parser.add_argument("--videos", type=Path, default=ROOT / "data" / "downloads" / "ppe_videos")
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "expanded_ppe_kaggle")
    parser.add_argument("--weights", type=Path, default=ROOT / "runs" / "train" / "expanded-ppe-yolov8s-hardcase12" / "weights" / "best.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "e8_ppe_v1")
    parser.add_argument("--dataset-yaml", type=Path, default=ROOT / "data" / "expanded_ppe_e8.yaml")
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--device", default="0")
    parser.add_argument("--dark-limit", type=int, default=60)
    parser.add_argument("--small-limit", type=int, default=60)
    args = parser.parse_args()

    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"Output is not empty: {args.output}")
    if not args.weights.exists():
        raise FileNotFoundError(args.weights)

    image_dir = args.output / "images" / "train"
    label_dir = args.output / "labels" / "train"
    review_dir = args.output / "review"
    for directory in (image_dir, label_dir, review_dir):
        directory.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    video_records, video_sheets = process_videos(
        model=model,
        videos_dir=args.videos,
        image_dir=image_dir,
        label_dir=label_dir,
        review_dir=review_dir,
        inference_size=args.imgsz,
        device=args.device,
    )
    mined_records, mined_sheets = mine_train_helmets(
        base_root=args.base,
        image_dir=image_dir,
        label_dir=label_dir,
        review_dir=review_dir,
        dark_limit=args.dark_limit,
        small_limit=args.small_limit,
    )
    records = video_records + mined_records
    class_counts = {
        name: sum(int(record["class_counts"].get(name, 0)) for record in records)
        for name in CLASS_NAMES.values()
    }
    kind_counts: dict[str, int] = {}
    for record in records:
        kind = str(record["kind"])
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    source_manifest = args.videos / "manifest.json"
    payload = {
        "dataset": "E8 PPE video hard cases",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classes": CLASS_NAMES,
        "weights": {"path": str(args.weights.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(args.weights)},
        "video_manifest": {
            "path": str(source_manifest.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(source_manifest),
        },
        "annotation": {
            "video_positive": "E7 model-assisted labels at high resolution with class thresholds and person-PPE spatial filtering; review sheets required before training",
            "video_negative": "Empty labels from visually reviewed machinery-only sources",
            "mined_samples": "Existing labels copied only from the original train split for controlled oversampling",
        },
        "limitations": [
            "Video frames from one source are correlated and are not counted as independent scenes.",
            "Pseudo labels are not independent ground truth and cannot be used as test metrics.",
            "Mined samples intentionally duplicate train-split content and must not be reported as new images.",
        ],
        "counts": {"images": len(records), "kinds": kind_counts, "classes": class_counts},
        "review_sheets": {**video_sheets, **mined_sheets},
        "samples": [manifest_record(record, args.output) for record in records],
    }
    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_dataset_yaml(args.dataset_yaml, args.base, args.output)
    print(json.dumps({"output": str(args.output), "dataset_yaml": str(args.dataset_yaml), "counts": payload["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
