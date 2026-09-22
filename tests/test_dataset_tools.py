from __future__ import annotations

from pathlib import Path

from PIL import Image

from scripts.download_kaggle_dataset import _normalise_yolo, _resolve_split


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24), color=(40, 80, 120)).save(path)


def test_resolve_split_accepts_roboflow_valid_alias(tmp_path: Path):
    source = tmp_path / "source"
    yaml_path = source / "data.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(
        "train: ../train/images\nval: ../valid/images\ntest: ../test/images\n"
        "names: [Person, Hard_hat, Vest]\n",
        encoding="utf-8",
    )
    _write_image(source / "valid" / "images" / "sample.jpg")

    resolved = _resolve_split(yaml_path, source, "../valid/images", "val")

    assert resolved == source / "valid" / "images"


def test_normalise_yolo_preserves_valid_split_and_target_mapping(tmp_path: Path):
    source = tmp_path / "source"
    yaml_path = source / "data.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(
        "train: ../train/images\nval: ../valid/images\ntest: ../test/images\n"
        "names: [Gloves, Hard_hat, Mask, Person, Safety_boots, Vest]\n",
        encoding="utf-8",
    )
    for split in ("train", "valid", "test"):
        image = source / split / "images" / f"{split}.jpg"
        _write_image(image)
        (source / split / "labels").mkdir(parents=True, exist_ok=True)
        (source / split / "labels" / f"{split}.txt").write_text(
            "1 0.5 0.4 0.2 0.2\n3 0.5 0.5 0.5 0.8\n5 0.5 0.7 0.4 0.3\n0 0.1 0.1 0.1 0.1\n",
            encoding="utf-8",
        )

    summary = _normalise_yolo(source, tmp_path / "output", yaml_path, force=False)

    assert summary["splits"]["val"]["images"] == 1
    assert summary["splits"]["val"]["boxes"] == 3
    assert summary["splits"]["val"]["skipped_boxes"] == 1
    assert (tmp_path / "output" / "images" / "val" / "kaggle_val_valid.jpg").exists()
