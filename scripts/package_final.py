"""打包期末提交：可运行系统全部代码 + 演示视频（视频置于压缩包根目录）。"""

import os
import zipfile
from pathlib import Path

ROOT = Path(r"D:\UserData\19505\Documents\ChatGPT\cucn_homework")
OUT = Path(r"C:\Users\19505\Desktop\Z202508090311_朱文杰《基于机器学习的工业安全智能监测系统》.zip")

INCLUDE_DIRS = ["app", "backend-java/src", "backend-java/.mvn", "frontend/src", "docs", "scripts", "tests", "data/demo"]
INCLUDE_FILES = [
    "backend-java/pom.xml",
    "frontend/package.json", "frontend/package-lock.json", "frontend/vite.config.js",
    "frontend/index.html", "frontend/nginx.conf", "frontend/Dockerfile", "frontend/.gitignore",
    "data/construction_ppe.yaml", "data/dataset_sources.json",
    "data/expanded_ppe_kaggle/dataset.yaml",
    "models/expanded-ppe-yolov8s-hardcase12.pt",
    "requirements.txt", "requirements-dev.txt", ".python-version", ".env.example",
    "Dockerfile", "docker-compose.yml", "docker-compose.gpu.yml", ".dockerignore",
    "README.md", ".gitignore",
    "results/expanded-ppe-yolov8s-hardcase12-test-metrics.json",
    "results/e8-video150-gate-review.json",
]
EXCLUDE_PARTS = {"__pycache__", "node_modules", "target", "logs", ".vite"}
VIDEO = ROOT / "results/final/系统演示视频.mp4"


def main() -> None:
    count, total = 0, 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for d in INCLUDE_DIRS:
            base = ROOT / d
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file() or any(part in EXCLUDE_PARTS for part in path.parts):
                    continue
                zf.write(path, Path(d) / path.relative_to(base))
                count += 1
                total += path.stat().st_size
        for f in INCLUDE_FILES:
            path = ROOT / f
            if path.is_file():
                zf.write(path, f)
                count += 1
                total += path.stat().st_size
        if VIDEO.is_file():
            zf.write(VIDEO, "系统演示视频.mp4")
            count += 1
            total += VIDEO.stat().st_size
    print(f"打包完成: {OUT.name}")
    print(f"文件数 {count} | 原始 {total/1048576:.1f} MB | 压缩后 {OUT.stat().st_size/1048576:.1f} MB")


if __name__ == "__main__":
    main()
