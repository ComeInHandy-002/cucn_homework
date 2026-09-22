from __future__ import annotations

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8 on the prepared PPE dataset.")
    parser.add_argument("--model", default="yolov8s.pt", help="YOLO base model, for example yolov8n.pt or yolov8s.pt")
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data" / "construction_ppe.yaml"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0, help="Dataloader workers; use 0 on Windows to avoid CUDA DLL worker overhead")
    parser.add_argument(
        "--cache",
        choices=["none", "ram", "disk"],
        default="none",
        help="Cache training images to reduce data-loader stalls.",
    )
    parser.add_argument("--name", default=None)
    parser.add_argument("--optimizer", default="auto", help="Ultralytics optimizer name, e.g. auto or AdamW")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    parser.add_argument("--lrf", type=float, default=0.01, help="Final learning-rate fraction")
    parser.add_argument("--warmup-epochs", type=float, default=3.0)
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument("--patience", type=int, default=100)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume optimizer and scheduler state from the supplied checkpoint.",
    )
    args = parser.parse_args()

    from ultralytics import YOLO

    model_name = args.name or Path(args.model).stem + "-construction-ppe"
    model = YOLO(args.model)
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=max(0, args.workers),
        cache=False if args.cache == "none" else args.cache,
        optimizer=args.optimizer,
        lr0=args.lr0,
        lrf=args.lrf,
        warmup_epochs=max(0.0, args.warmup_epochs),
        close_mosaic=max(0, args.close_mosaic),
        patience=max(0, args.patience),
        project=str(PROJECT_ROOT / "runs" / "train"),
        name=model_name,
        exist_ok=True,
        resume=args.resume,
    )
    print(results)


if __name__ == "__main__":
    main()
