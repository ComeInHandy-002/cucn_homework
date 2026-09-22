"""Build a provenance-preserving YOLO dataset from the prepared PPE sources.

The source datasets stay untouched.  Files are copied into a new directory with
source prefixes so that similarly named Roboflow images cannot overwrite one
another.  The manifest records image/box counts and duplicate image hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(source: Path, split: str, prefix: str) -> list[tuple[Path, Path, str]]:
    image_root = source / "images" / split
    label_root = source / "labels" / split
    rows: list[tuple[Path, Path, str]] = []
    for image in sorted(image_root.iterdir()):
        if not image.is_file() or image.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        target_stem = f"{prefix}_{image.stem}"
        label = label_root / f"{image.stem}.txt"
        rows.append((image, label, target_stem))
    return rows


def copy_split(
    target: Path,
    split: str,
    sources: list[tuple[Path, str]],
    seen_hashes: dict[str, str],
) -> dict[str, object]:
    image_dir = target / "images" / split
    label_dir = target / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    hashes: dict[str, str] = {}
    duplicate_hashes: dict[str, list[str]] = {}
    for source_root, prefix in sources:
        for image, label, target_stem in collect(source_root, split, prefix):
            digest = sha256(image)
            relative_source = f"{prefix}/{split}/{image.name}"
            if digest in seen_hashes:
                duplicate_hashes.setdefault(digest, [seen_hashes[digest]]).append(relative_source)
                counts["duplicates_skipped"] += 1
                continue
            seen_hashes[digest] = relative_source
            target_image = image_dir / f"{target_stem}{image.suffix.lower()}"
            target_label = label_dir / f"{target_stem}.txt"
            shutil.copy2(image, target_image)
            if label.exists():
                shutil.copy2(label, target_label)
            else:
                target_label.write_text("", encoding="utf-8")
            relative = target_image.relative_to(target).as_posix()
            hashes[digest] = relative
            counts["images"] += 1
            rows = [line for line in target_label.read_text(encoding="utf-8").splitlines() if line.strip()]
            counts["boxes"] += len(rows)
            for row in rows:
                class_id = row.split()[0]
                counts[f"class_{class_id}"] += 1
            if not rows:
                counts["empty_labels"] += 1
    return {"counts": dict(counts), "duplicate_image_hashes": duplicate_hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge normalized PPE datasets without modifying their sources.")
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "expanded_ppe")
    parser.add_argument("--kaggle", type=Path, default=ROOT / "data" / "kaggle_ppe")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "expanded_ppe_kaggle")
    parser.add_argument("--force", action="store_true", help="Replace only the generated output directory.")
    args = parser.parse_args()
    if args.output.exists():
        if not args.force:
            raise SystemExit(f"output exists: {args.output}; pass --force to rebuild it")
        shutil.rmtree(args.output)
    for source in (args.base, args.kaggle):
        if not (source / "images").is_dir() or not (source / "labels").is_dir():
            raise SystemExit(f"normalized dataset not found: {source}")
    args.output.mkdir(parents=True, exist_ok=True)
    splits: dict[str, object] = {}
    seen_hashes: dict[str, str] = {}
    for split in ("train", "val", "test"):
        splits[split] = copy_split(args.output, split, [(args.base, "expanded"), (args.kaggle, "kaggle")], seen_hashes)
    yaml_path = args.output / "dataset.yaml"
    yaml_path.write_text(
        "path: " + args.output.resolve().as_posix() + "\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: person\n  1: helmet\n  2: vest\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_name": "Expanded PPE + Kaggle PPE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"name": "Expanded PPE (Construction-PPE + SH17)", "path": str(args.base.resolve())},
            {"name": "Kaggle PPE Detection", "handle": "uzairahmad1434/ppe-detection", "path": str(args.kaggle.resolve())},
        ],
        "target_classes": ["person", "helmet", "vest"],
        "splits": splits,
        "dataset_yaml": str(yaml_path.resolve()),
        "notes": "Generated copy only; source directories are not modified. Duplicate image hashes are reported per split.",
    }
    (args.output / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
