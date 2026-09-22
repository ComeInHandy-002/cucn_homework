"""Download and audit a public Kaggle PPE dataset.

This helper intentionally keeps Kaggle optional.  The project can be rebuilt
from the Hugging Face SH17 mirror without credentials; this script is for
users who want to obtain the same (or another public PPE) dataset through
Kaggle.  ``kagglehub`` is imported lazily so the normal application install
does not gain a large, unrelated dependency.

The downloaded tree is never mixed into ``data/expanded_ppe`` automatically.
With ``--normalize-yolo`` a three-class YOLO copy is written to the separate
``data/kaggle_ppe`` directory after the source has been inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = "mugheesahmad/sh17-dataset-for-ppe-detection"
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "data" / "downloads" / "kaggle" / "sh17"
DEFAULT_NORMALIZED_DIR = PROJECT_ROOT / "data" / "kaggle_ppe"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
METADATA_EXTENSIONS = {".json", ".yaml", ".yml", ".txt", ".md"}
TARGET_NAMES = ["person", "helmet", "vest"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a data.yaml without making PyYAML a hard dependency."""

    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (ImportError, OSError, ValueError):
        payload: dict[str, Any] = {}
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        in_names = False
        names: dict[int, str] = {}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "names:":
                in_names = True
                continue
            if in_names:
                match = re.match(r"^(\d+)\s*:\s*[\"']?(.+?)[\"']?$", stripped)
                if match:
                    names[int(match.group(1))] = match.group(2).strip()
                    continue
                if not line.startswith((" ", "\t")):
                    in_names = False
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                value = value.strip().strip("\"'")
                if key in {"path", "train", "val", "test"}:
                    payload[key] = value
        if names:
            payload["names"] = names
        return payload


def _class_names(payload: dict[str, Any]) -> list[str]:
    names = payload.get("names", [])
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names, key=lambda item: int(item))]
    if isinstance(names, list):
        return [str(name) for name in names]
    return []


def _normalise_class(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _target_class_map(names: list[str]) -> dict[int, int]:
    aliases = {
        "person": {"person", "people", "worker", "human"},
        "helmet": {"helmet", "hardhat", "safetyhelmet", "hardhathelmet"},
        "vest": {"vest", "safetyvest", "reflectivevest", "reflectivejacket"},
    }
    result: dict[int, int] = {}
    for index, name in enumerate(names):
        normalised = _normalise_class(name)
        for target_index, target in enumerate(TARGET_NAMES):
            if normalised in aliases[target]:
                result[index] = target_index
                break
    return result


def _find_metadata(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name != "kaggle_manifest.json"
        and path.suffix.lower() in METADATA_EXTENSIONS
    )


def _find_yaml(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name.lower() in {"data.yaml", "dataset.yaml"}
    )


def _find_coco(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.json")
        if "annotation" in path.name.lower() or "coco" in path.name.lower()
    )


def _inventory(root: Path) -> dict[str, Any]:
    yaml_files = _find_yaml(root)
    coco_files = _find_coco(root)
    image_count = sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    label_count = sum(1 for path in root.rglob("*.txt") if path.name.lower() != "readme.dataset.txt")
    payload: dict[str, Any] = {
        "format": "yolo" if yaml_files else ("coco" if coco_files else "unknown"),
        "images": image_count,
        "label_files": label_count,
        "yaml_files": [str(path.relative_to(root)) for path in yaml_files],
        "coco_files": [str(path.relative_to(root)) for path in coco_files],
        "class_names": [],
        "target_class_map": {},
    }
    if yaml_files:
        names = _class_names(_read_yaml(yaml_files[0]))
        payload["class_names"] = names
        payload["target_class_map"] = {
            str(source): target for source, target in _target_class_map(names).items()
        }
    return payload


def _download_with_kagglehub(handle: str, destination: Path, version: int | None, force: bool) -> Path:
    try:
        import kagglehub  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "缺少可选依赖 kagglehub。先执行 `uv pip install kagglehub`，"
            "或使用 --dry-run 查看不下载的复现命令。"
        ) from exc

    kwargs: dict[str, Any] = {"force_download": force}
    if version is not None:
        kwargs["version"] = version
    try:
        cached = Path(kagglehub.dataset_download(handle, **kwargs))
    except TypeError:
        # Older kagglehub releases do not expose ``version``.
        kwargs.pop("version", None)
        cached = Path(kagglehub.dataset_download(handle, **kwargs))
    if not cached.exists():
        raise RuntimeError(f"kagglehub returned a missing path: {cached}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and force:
        shutil.rmtree(destination)
    if destination.resolve() != cached.resolve():
        shutil.copytree(cached, destination, dirs_exist_ok=True)
    return destination


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _candidate_label_paths(image: Path, root: Path) -> Iterable[Path]:
    relative = image.relative_to(root)
    parts = list(relative.parts)
    for index, part in enumerate(parts):
        if part.lower() == "images":
            candidate = list(parts)
            candidate[index] = "labels"
            candidate[-1] = f"{Path(candidate[-1]).stem}.txt"
            yield root.joinpath(*candidate)
    yield image.with_suffix(".txt")
    yield root / "labels" / f"{image.stem}.txt"


def _resolve_split(yaml_path: Path, root: Path, value: Any, split: str) -> Path | None:
    candidates: list[Path] = []
    if isinstance(value, list):
        candidates.extend(Path(str(item)) for item in value)
    elif value:
        candidates.append(Path(str(value)))
    # Roboflow/Kaggle exports use both ``val`` and ``valid``.  Keep the
    # output split name stable while accepting either source spelling.
    split_aliases = {
        "train": ("train",),
        "val": ("val", "valid", "validation"),
        "test": ("test",),
    }
    for alias in split_aliases.get(split, (split,)):
        candidates.extend(
            [
                Path(alias) / "images",
                Path("images") / alias,
                Path(alias),
            ]
        )
    yaml_payload = _read_yaml(yaml_path)
    base_value = yaml_payload.get("path")
    configured_base = Path(str(base_value)) if base_value else yaml_path.parent
    if not configured_base.is_absolute():
        configured_base = yaml_path.parent / configured_base
    # Kaggle exports sometimes preserve a hosted `/kaggle/input/...` path.
    # Try that value first, then resolve the same split relative to the local
    # downloaded root so the export remains portable.
    bases = [configured_base, root, yaml_path.parent]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate_bases = [candidate] if candidate.is_absolute() else [base / candidate for base in bases]
        for path in candidate_bases:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if path.exists():
                images = [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS]
                if images:
                    return path
    return None


def _normalise_yolo(source: Path, output: Path, yaml_path: Path, force: bool) -> dict[str, Any]:
    payload = _read_yaml(yaml_path)
    names = _class_names(payload)
    class_map = _target_class_map(names)
    if not class_map:
        raise RuntimeError(f"未找到 person/helmet/vest 类别，实际类别为: {names}")
    if output.exists() and force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {}
    for split in ("train", "val", "test"):
        split_root = _resolve_split(yaml_path, source, payload.get(split), split)
        if split_root is None:
            summary[split] = {"images": 0, "boxes": 0, "skipped_boxes": 0}
            continue
        image_output = output / "images" / split
        label_output = output / "labels" / split
        image_output.mkdir(parents=True, exist_ok=True)
        label_output.mkdir(parents=True, exist_ok=True)
        counts = {"images": 0, "boxes": 0, "skipped_boxes": 0}
        for image in sorted(split_root.rglob("*")):
            if not image.is_file() or image.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative = image.relative_to(split_root)
            # Flatten nested source directories while retaining enough of the
            # original path to avoid overwriting same-named images.
            flattened = "__".join(re.sub(r"[^a-zA-Z0-9._-]", "_", part) for part in relative.parts)
            target_name = f"kaggle_{split}_{flattened}"
            target_image = image_output / target_name
            target_label = label_output / f"{Path(target_name).stem}.txt"
            shutil.copy2(image, target_image)
            rows: list[str] = []
            label_path = next((candidate for candidate in _candidate_label_paths(image, source) if candidate.exists()), None)
            if label_path:
                for line in label_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    fields = line.split()
                    if len(fields) != 5:
                        counts["skipped_boxes"] += 1
                        continue
                    try:
                        source_id = int(fields[0])
                        values = [float(value) for value in fields[1:]]
                    except ValueError:
                        counts["skipped_boxes"] += 1
                        continue
                    if source_id not in class_map or any(value < 0 or value > 1 for value in values):
                        counts["skipped_boxes"] += 1
                        continue
                    rows.append(f"{class_map[source_id]} {' '.join(f'{value:.6f}' for value in values)}")
            target_label.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
            counts["images"] += 1
            counts["boxes"] += len(rows)
        summary[split] = counts

    yaml_output = output / "dataset.yaml"
    yaml_output.write_text(
        "path: " + output.resolve().as_posix() + "\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n  0: person\n  1: helmet\n  2: vest\n",
        encoding="utf-8",
    )
    return {"output": str(output.resolve()), "dataset_yaml": str(yaml_output.resolve()), "splits": summary, "class_map": class_map}


def _write_manifest(root: Path, handle: str, inventory: dict[str, Any], version: int | None) -> Path:
    metadata_hashes: dict[str, str] = {}
    for path in _find_metadata(root):
        try:
            metadata_hashes[_safe_relative(path, root)] = _sha256(path)
        except OSError:
            continue
    manifest = {
        "dataset_handle": handle,
        "dataset_version": version,
        "provider": "Kaggle via kagglehub",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "local_dir": str(root.resolve()),
        "inventory": inventory,
        "metadata_sha256": metadata_hashes,
        "notes": [
            "Kaggle files are optional input and are not merged into data/expanded_ppe automatically.",
            "Verify the dataset page license and citation before redistribution or publication.",
        ],
    }
    target = root / "kaggle_manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and audit a public Kaggle PPE dataset.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Kaggle dataset handle owner/dataset")
    parser.add_argument("--version", type=int, default=None, help="Optional Kaggle dataset version")
    parser.add_argument("--output", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--normalize-yolo", action="store_true", help="Create an isolated three-class YOLO copy")
    parser.add_argument("--normalized-output", type=Path, default=DEFAULT_NORMALIZED_DIR)
    parser.add_argument("--force", action="store_true", help="Redownload and replace output copies")
    parser.add_argument("--dry-run", action="store_true", help="Print the command and exit without network access")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(json.dumps({
            "dataset": args.dataset,
            "output": str(args.output),
            "next": "uv pip install kagglehub && python scripts/download_kaggle_dataset.py",
            "normalization": str(args.normalized_output) if args.normalize_yolo else None,
        }, ensure_ascii=False, indent=2))
        return 0

    root = _download_with_kagglehub(args.dataset, args.output, args.version, args.force)
    inventory = _inventory(root)
    manifest = _write_manifest(root, args.dataset, inventory, args.version)
    result: dict[str, Any] = {"download": str(root.resolve()), "manifest": str(manifest.resolve()), "inventory": inventory}
    if args.normalize_yolo:
        yaml_files = _find_yaml(root)
        if not yaml_files:
            raise RuntimeError("Kaggle 数据未发现 data.yaml/dataset.yaml，当前只支持带 YOLO 配置的下载目录归一化")
        result["normalized"] = _normalise_yolo(root, args.normalized_output, yaml_files[0], args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
