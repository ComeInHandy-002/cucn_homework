from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy a trained YOLO model into the service models directory.")
    parser.add_argument("--weights", required=True, help="Path to best.pt from a training run")
    parser.add_argument("--target", default=str(PROJECT_ROOT / "models" / "yolov8s.pt"))
    args = parser.parse_args()

    source = Path(args.weights)
    if not source.exists():
        raise FileNotFoundError(source)
    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"exported {source} -> {target}")


if __name__ == "__main__":
    main()
