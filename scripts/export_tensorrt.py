"""Explicitly export a trained Ultralytics model to a TensorRT FP16 engine.

TensorRT export is intentionally a separate command: it can take substantial
GPU memory and requires a compatible TensorRT/CUDA installation.  The API
uses an ``.engine`` only when ``MODEL_PATH`` points at the generated file.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export YOLO weights as a TensorRT FP16 engine.")
    parser.add_argument("--weights", type=Path, required=True, help="Path to a trained .pt file")
    parser.add_argument("--output", type=Path, default=None, help="Optional destination .engine path")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workspace", type=float, default=4.0, help="TensorRT workspace in GiB")
    parser.add_argument("--dynamic", action="store_true", help="Build a dynamic-shape engine")
    args = parser.parse_args(argv)

    weights = args.weights.resolve()
    if not weights.is_file():
        raise FileNotFoundError(weights)
    try:
        from ultralytics import YOLO  # type: ignore

        model = YOLO(str(weights))
        exported = model.export(
            format="engine",
            half=True,
            imgsz=args.imgsz,
            batch=max(1, args.batch),
            device=args.device,
            workspace=args.workspace,
            dynamic=args.dynamic,
        )
    except Exception as exc:
        raise RuntimeError(
            "TensorRT FP16 export failed. Install a CUDA/TensorRT version compatible "
            f"with Ultralytics, then retry: {exc}"
        ) from exc

    exported_path = Path(str(exported)).resolve()
    if args.output is not None:
        target = args.output.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exported_path, target)
        exported_path = target
    print(f"TensorRT FP16 engine: {exported_path}")
    print("Set MODEL_PATH to this .engine file and restart the API to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
