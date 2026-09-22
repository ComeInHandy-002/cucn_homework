from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLO weights and save thesis metrics as JSON.")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data" / "construction_ppe.yaml"))
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "metrics.json"))
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    metrics = model.val(data=args.data, split=args.split, imgsz=args.imgsz, device=args.device)
    precision = float(metrics.box.mp)
    recall = float(metrics.box.mr)
    payload = {
        "weights": args.weights,
        "data": args.data,
        "split": args.split,
        "imgsz": args.imgsz,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
    }
    class_names = getattr(metrics, "names", None) or getattr(model, "names", {})
    class_precision = getattr(metrics.box, "p", None)
    class_recall = getattr(metrics.box, "r", None)
    class_map50 = getattr(metrics.box, "ap50", None)
    if class_precision is not None and class_recall is not None:
        try:
            p_values = class_precision.tolist()
            r_values = class_recall.tolist()
            ap_values = class_map50.tolist() if class_map50 is not None else []
            payload["per_class"] = {}
            for index, (p_value, r_value) in enumerate(zip(p_values, r_values)):
                name = class_names.get(index, str(index)) if hasattr(class_names, "get") else str(index)
                payload["per_class"][str(name)] = {
                    "precision": float(p_value),
                    "recall": float(r_value),
                    "f1": 2 * float(p_value) * float(r_value) / (float(p_value) + float(r_value)) if float(p_value) + float(r_value) else 0.0,
                    "map50": float(ap_values[index]) if index < len(ap_values) else None,
                }
        except (AttributeError, TypeError, ValueError):
            # Keep aggregate metrics available for older Ultralytics releases.
            pass
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
