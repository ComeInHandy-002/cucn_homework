# 工业安全智能监测系统

基于 YOLOv8 与 ByteTrack 思路的工业作业人员安全防护与危险区域智能监测系统。系统面向结课大作业和毕设原型，覆盖模型推理、人员跟踪、PPE 关联、危险区域规则、告警入库、接口服务和最小可用工作台。

## 功能范围

- 人员、安全帽、反光背心检测。
- 人员稳定 `track_id` 分配。
- 人员框与 PPE 框空间关联。
- 危险区域多边形配置与脚底中心点越界判断。
- 视频模式连续 3 帧确认，同一人员同一规则 10 秒冷却。
- JWT 登录、摄像头配置、推理任务、告警查询处理、统计摘要。
- 深色工业监控工作台：监控总览、智能检测、任务中心、模型实验、告警中心、设备与区域六个页面；支持实时 WebSocket 提示、证据弹窗、内置演示素材一键载入和危险区画布点选。
- 无本地 YOLO 权重时自动进入 fallback 演示模式，不下载模型、不伪造训练结果。
- 视频链路采用有界解码/批量推理/顺序跟踪与编码流水线；默认 batch=8，CUDA 自动启用 FP16。

## 快速启动

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

完整文档索引见 `docs/INDEX.md`，环境说明见 `docs/SETUP.md`。现场演示按 `docs/DEMO_GUIDE.md`，答辩讲解按 `docs/PRESENTATION_SCRIPT.md`，前端逐项校验见 `docs/FRONTEND_VALIDATION.md`。项目固定使用 Python 3.12；没有 NVIDIA GPU 时仍可用 CPU/fallback 完成接口和规则演示。

访问 `http://127.0.0.1:8000/`；若 8000 已被其他程序占用，改用 `--port 8010` 并访问 `http://127.0.0.1:8010/`。

默认开发账号：`admin` / `admin123`。生产或答辩部署前必须修改 `.env` 中的 `SECRET_KEY` 和默认密码逻辑。

## 模型权重

当前仓库保留多个可回滚权重。服务实际使用哪一个以 `.env` 的 `MODEL_PATH` 和
`GET /health` 返回值为准；切换权重后必须重启服务并做图片/视频回归，不要只改文档。

当前默认配置使用在 Expanded PPE + Kaggle PPE 基础上加入定向 hard-case 后完成 12 epoch GPU 精调的 YOLOv8s 权重：

```text
models/expanded-ppe-yolov8s-hardcase12.pt
```

原 Construction-PPE 权重、5/10 epoch 对照权重和 E6 合并集权重均保留用于复现与回滚。当前默认配置在未参与 hard-case 增强的合并集 test split 上取得 Precision 0.7977、Recall 0.6620、F1 0.7235、mAP@0.5 0.7200、mAP@0.5:0.95 0.4441；helmet Recall 为 0.4548。证据位于 `results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`。三张用户抽查原图的定向门禁和两段视频回归均通过，分别见 `results/hardcase-regression-hardcase12.json` 与 `results/video-regression-hardcase12.json`；它们不属于独立泛化指标。如果训练权重不存在，服务会使用 deterministic fallback detector，方便演示接口、规则引擎和前端流程；fallback 不是模型实验结果。

## 视频推理性能配置

`.env` 默认使用 `VIDEO_BATCH_SIZE=8`、`VIDEO_QUEUE_SIZE=16` 和 `VIDEO_HALF=true`。
检测器按批运行，但 ByteTrack、连续帧确认和告警规则仍严格按原始 `frame_index`
逐帧执行。`VIDEO_DECODE_BACKEND=auto` 与 `VIDEO_ENCODE_BACKEND=auto` 会优先选择
FFmpeg；只有本机 FFmpeg 实际支持 CUDA/NVENC 时才使用 NVDEC/NVENC，否则自动回退
到 FFmpeg CPU 或 OpenCV。`GET /health` 的 detector 信息和结果 JSON 的 `metrics`
会记录实际后端、batch、FP16/TensorRT 状态及各阶段耗时。

多视频并发由 `QUEUE_WORKERS` 请求、`MAX_VIDEO_WORKERS` 硬上限和
`VIDEO_WORKER_MEMORY_MB` 显存预算共同控制。每个 worker 单独加载模型；RTX 4070
Laptop 8 GB 默认保持 1，不应直接提高 worker 数。TensorRT 必须显式导出：

```powershell
.\.venv\Scripts\python.exe scripts\export_tensorrt.py `
  --weights models\expanded-ppe-yolov8s-hardcase12.pt `
  --output models\expanded-ppe-yolov8s-hardcase12-fp16.engine `
  --imgsz 640 --batch 8 --device 0
```

导出成功后再把 `MODEL_PATH` 指向 `.engine` 并设置 `VIDEO_TENSORRT=true`。当前正在
训练或 TensorRT 环境未安装时不要执行导出；PyTorch FP16 路径仍可直接使用。

## 扩充训练数据

项目已准备两份互不覆盖的数据产物：

- `data/expanded_ppe/`：Construction-PPE + SH17，9,515 张图片、24,716 个框，用于 E4/E5 对照。
- `data/expanded_ppe_kaggle/`：在上述扩充集基础上合并 Kaggle PPE Detection，并按图片 SHA256 去重，11,623 张图片、28,853 个框；其 val/test 保持为独立评估划分。
- `data/hard_cases/`：3 张用户抽查原图及每图 60 个确定性增强，共 183 张训练图、1,037 个框，仅挂载到训练集。增强图不能视为 183 个独立场景，也不进入 val/test。

两份数据都统一为 `person / helmet / vest` 三类；来源、许可证、类别映射和 SHA256
必须以各自清单和校验报告为准。合并集质量报告为
`results/expanded_ppe_kaggle_validation_latest.json`，旧扩充集报告为
`results/expanded_ppe_validation.json`。

使用扩充数据训练时（Windows 建议 `--workers 0`，避免 CUDA DLL 被多进程重复加载）：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo.py --data data/expanded_ppe/dataset.yaml --model yolov8s.pt --workers 0 --name expanded-ppe-yolov8s
```

训练完成后，再用 `scripts/evaluate_yolo.py` 对对应 `dataset.yaml` 的 test split 生成真实指标；不要把数据准备结果当作模型指标。E6 历史对照与 E7 当前模型的复现命令、独立 test 和定向回归边界见 `docs/EXPERIMENTS.md`。

如需按常见的 Kaggle 流程获取公开 SH17 数据，可使用可选脚本：

```powershell
uv pip install kagglehub
.\.venv\Scripts\python.exe scripts\download_kaggle_dataset.py --normalize-yolo
```

Kaggle 文件会单独保存到 `data/downloads/kaggle/`，归一化结果默认写入 `data/kaggle_ppe/`，不会覆盖当前 `data/expanded_ppe/`。脚本会生成 `kaggle_manifest.json`，记录版本、格式、类别映射和元数据 SHA256；下载后先运行 `scripts/validate_dataset.py`，核对许可证和数量后再单独训练。无 Kaggle 账号或不需要 Kaggle 时，继续使用上面的 Hugging Face 镜像复现路径即可。详细说明见 [`docs/KAGGLE_DATA.md`](docs/KAGGLE_DATA.md)。

要复现当前合并实验，在归一化完成后执行：

```powershell
.\.venv\Scripts\python.exe scripts\merge_ppe_datasets.py `
  --base data\expanded_ppe --kaggle data\kaggle_ppe `
  --output data\expanded_ppe_kaggle
```

合并集的数量和去重记录以 `data/expanded_ppe_kaggle/dataset_manifest.json` 与
`results/expanded_ppe_kaggle_validation_latest.json` 为准。

## Docker

```powershell
docker compose up --build
```

Compose 默认连接 PostgreSQL，并将 `models/`、`uploads/`、`results/`、`data/` 作为 volume 保存。

## API 概览

- `POST /api/v1/auth/login`
- `POST /api/v1/inference/images`
- `POST /api/v1/inference/videos`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/result`
- `GET /api/v1/events`
- `PATCH /api/v1/events/{event_id}`
- `GET /api/v1/jobs`
- `GET /api/v1/experiments/summary`
- `GET /api/v1/demo/assets`
- `POST /api/v1/cameras`
- `GET /api/v1/cameras`
- `POST /api/v1/cameras/{camera_id}/zones`
- `GET /api/v1/zones`
- `DELETE /api/v1/zones/{zone_id}`
- `GET /api/v1/metrics/summary`
- `WS /api/v1/ws/events`

详细契约见 `docs/API.md`。现场演示按 `docs/DEMO_GUIDE.md`，答辩讲解按 `docs/PRESENTATION_SCRIPT.md`，提交前按 `docs/DELIVERY_CHECKLIST.md`。

## 目录结构

```text
app/
  api/          FastAPI routes
  core/         detector, tracker, rule engine, schemas
  db/           SQLAlchemy setup and persistence models
  services/     inference orchestration
  static/       browser workstation
data/           dataset notes and local samples
models/         local YOLO weights
uploads/        uploaded images/videos
results/        result JSON, annotated images/videos, evidence screenshots
tests/          core and API tests
docs/           API, dataset and experiment documentation
scripts/        reproducible demo and benchmark helpers
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
.\.venv\Scripts\python.exe -m pytest -q
```

## 毕设材料边界

当前仓库已提供可运行工程、E1-E7 可复现实验、独立 test 指标与定向图片/视频回归。论文可引用已生成的 Precision、Recall、F1 和 mAP，但必须同时注明数据版本、训练轮数和测试划分；80 epoch 长周期实验、300–500 帧独立自建场景集、正式 720p 性能验收及消融实验仍未完成，不能用 fallback 或计划值替代。
