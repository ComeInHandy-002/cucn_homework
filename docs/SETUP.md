# 运行环境配置

## 推荐本地环境

- Windows 10/11
- Python 3.12.x（仓库通过 `.python-version` 固定为 3.12.13）
- `uv` 0.9 或更高版本
- Docker Desktop（仅在需要 PostgreSQL Compose 部署时使用）
- NVIDIA GPU：可选；没有 GPU 时仍可使用 fallback/CPU 推理

初始化开发环境：

```powershell
.\scripts\setup.ps1
```

脚本会创建 `.venv`、安装 `requirements-dev.txt`、生成本地 `.env`，并运行环境自检。手动方式：

```powershell
uv venv .venv --python 3.12.13
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.venv\Scripts\python.exe scripts\check_environment.py
```

## GPU 推理（可选）

先确认 `nvidia-smi` 能看到显卡，再执行：

```powershell
.\scripts\setup.ps1 -Gpu
```

该选项会从 PyTorch CUDA 12.6 索引安装 `torch==2.6.0+cu126` 和对应 TorchVision。安装包约数 GB，网络中断时可先使用默认 CPU 环境，不会影响 API 和 fallback 演示。当前工作站已验证 RTX 4070 Laptop GPU、CUDA 12.6 可用。验证：

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

## 模型权重

服务实际读取 `.env` 中的 `MODEL_PATH`；启动后以 `/health` 返回的 `model_path`、
`image_size` 和 `detector_backend` 为准。当前仓库默认配置已切换到
`models/expanded-ppe-yolov8s-hardcase12.pt`（合并集加定向 hard-case 的 12 epoch GPU 精调）。
当前部署副本 SHA256：`73CD31A09209C3F9B0375210160873B014F69F5FFF6B7B82EFA254C57D630E4F`。
其训练权重和独立 test 结果分别为：

```text
runs/train/expanded-ppe-yolov8s-hardcase12/weights/best.pt
results/expanded-ppe-yolov8s-hardcase12-test-metrics.json
```

E7 在合并集训练划分上追加 3 张抽查原图的 180 个增强版本，有效训练输入为 8,459 张、21,732 个框；独立 val/test 不变。12 epoch 训练的 best epoch 为 7，独立 test mAP@0.5 为 0.7200、helmet Recall 为 0.4548。完整指标、定向回归和复现命令见 `docs/EXPERIMENTS.md`。
E6 8 epoch、旧集 5/10 epoch 和官方基础权重仍保留用于回滚和对照。没有训练权重时服务自动使用
deterministic fallback；这不会产生或冒充论文模型指标。

E8 已完成 30 epoch 候选训练，但复核后没有替换部署：其权重位于
`runs/train/expanded-ppe-yolov8s-e8-video150/weights/best.pt`，当前服务仍读取 E7
`models/expanded-ppe-yolov8s-hardcase12.pt`。E8 的同口径比较和不部署原因见
`results/e8-video150-gate-review.json`。

`docker-compose.yml` 已与本机默认配置同步到 E7 权重。容器仍使用 CPU 安全配置；要在容器内启用 CUDA，需同时使用 CUDA 基础镜像和 NVIDIA Container Toolkit，不能只把 `MODEL_DEVICE` 改为 `0`。

## 启动与验证

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

另开终端运行：

```powershell
.venv\Scripts\python.exe -m pytest -q
Invoke-RestMethod http://127.0.0.1:8000/health
```

Docker Desktop 未启动时，`docker compose up` 会报 daemon 连接错误；这属于 Docker 服务状态，不是项目代码或 Python 环境错误。
