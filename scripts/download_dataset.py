from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "downloads"
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
DATASET_DIR = EXTERNAL_DIR / "construction-ppe"
SOURCE_LOG = PROJECT_ROOT / "data" / "dataset_sources.json"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and is_valid_zip(destination):
        return
    temp_path = destination.with_suffix(destination.suffix + ".part")
    temp_path.unlink(missing_ok=True)
    print(f"Downloading {url} -> {destination}")
    total = _remote_size(url)
    chunk_size = 8 * 1024 * 1024
    with temp_path.open("wb") as output:
        offset = 0
        while offset < total:
            end = min(total - 1, offset + chunk_size - 1)
            for attempt in range(3):
                try:
                    request = Request(url, headers={"Range": f"bytes={offset}-{end}"})
                    with urlopen(request, timeout=120) as response:
                        payload = response.read()
                    expected = end - offset + 1
                    if len(payload) != expected:
                        raise IOError(f"short range response: got {len(payload)}, expected {expected}")
                    output.write(payload)
                    offset = end + 1
                    print(f"  {offset}/{total} bytes", flush=True)
                    break
                except (OSError, HTTPError) as exc:
                    if attempt == 2:
                        temp_path.unlink(missing_ok=True)
                        raise RuntimeError(f"dataset download failed at byte {offset}") from exc
                    sleep(2**attempt)
    if not is_valid_zip(temp_path):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("downloaded dataset is not a complete ZIP archive")
    temp_path.replace(destination)


def _remote_size(url: str) -> int:
    request = Request(url, method="HEAD")
    with urlopen(request, timeout=30) as response:
        size = response.headers.get("Content-Length")
    if not size or int(size) <= 0:
        raise RuntimeError("dataset server did not provide a valid Content-Length")
    return int(size)


def is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None and bool(archive.namelist())
    except zipfile.BadZipFile:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unpack_zip(zip_path: Path, output_dir: Path, force: bool = False) -> None:
    if force and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "data.yaml"
    if marker.exists() and not force:
        return
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(output_dir)


def rewrite_data_yaml(dataset_dir: Path) -> Path:
    source = dataset_dir / "data.yaml"
    if not source.exists():
        raise FileNotFoundError(f"missing dataset yaml: {source}")
    target = PROJECT_ROOT / "data" / "construction_ppe.yaml"
    text = source.read_text(encoding="utf-8")
    lines = []
    replaced_path = False
    for line in text.splitlines():
        if line.startswith("path:"):
            lines.append(f"path: {dataset_dir.as_posix()}")
            replaced_path = True
        else:
            lines.append(line)
    if not replaced_path:
        lines.insert(0, f"path: {dataset_dir.as_posix()}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def count_split(dataset_dir: Path, split: str) -> dict[str, int]:
    image_dir = dataset_dir / "images" / split
    label_dir = dataset_dir / "labels" / split
    if not image_dir.exists():
        image_dir = dataset_dir / split / "images"
        label_dir = dataset_dir / split / "labels"
    images = [path for path in image_dir.glob("*.*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    labels = list(label_dir.glob("*.txt")) if label_dir.exists() else []
    return {"images": len(images), "labels": len(labels)}


def write_source_log(url: str, zip_path: Path, yaml_path: Path, dataset_dir: Path) -> None:
    payload = {
        "name": "Construction-PPE",
        "source_url": url,
        "provider": "Ultralytics assets release",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "archive_bytes": zip_path.stat().st_size,
        "archive_sha256": sha256_file(zip_path),
        "local_dir": str(dataset_dir),
        "data_yaml": str(yaml_path),
        "classes": ["helmet", "gloves", "vest", "boots", "goggles", "none", "Person", "no_helmet", "no_goggle", "no_gloves", "no_boots"],
        "splits": {split: count_split(dataset_dir, split) for split in ["train", "val", "test"]},
        "notes": "Use only actual training/evaluation output for thesis metrics; fallback demo output is not a model result.",
    }
    SOURCE_LOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and prepare the Construction-PPE YOLO dataset.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    zip_path = DOWNLOAD_DIR / "construction-ppe.zip"
    download_file(args.url, zip_path)
    unpack_zip(zip_path, DATASET_DIR, force=args.force)
    yaml_path = rewrite_data_yaml(DATASET_DIR)
    write_source_log(args.url, zip_path, yaml_path, DATASET_DIR)
    print(json.dumps({"zip": str(zip_path), "dataset": str(DATASET_DIR), "yaml": str(yaml_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
