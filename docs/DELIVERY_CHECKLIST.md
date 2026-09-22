# 项目交付检查清单

## 源码与配置

- [x] `app/` 后端、推理、规则、跟踪和数据库代码
- [x] `app/static/` 前端工作台
- [x] `requirements.txt`、`requirements-dev.txt`
- [x] `.python-version`、`.env.example`
- [x] `Dockerfile`、`docker-compose.yml`

## 数据与模型

- [x] `data/external/construction-ppe/` 已下载并解压
- [x] `data/dataset_sources.json` 来源、许可证、SHA256 和数量记录
- [x] `results/dataset_validation.json` 数据校验结果
- [x] `models/construction-ppe-yolov8s.pt` Construction-PPE 对照权重
- [x] `models/expanded-ppe-yolov8s-hardcase12.pt` 当前默认服务权重（E7 12 epoch 定向精调）
- [x] 当前部署权重 SHA256 已记录：`73CD31A09209C3F9B0375210160873B014F69F5FFF6B7B82EFA254C57D630E4F`
- [x] `models/expanded-ppe-yolov8s-kaggle-refine8.pt` E6 历史部署权重，保留回滚
- [x] `models/yolov8n.pt`、`models/yolov8s.pt` 对照权重
- [x] `data/expanded_ppe/` 9,515 张图片、24,716 个框，三类目标质量校验通过
- [x] `data/expanded_ppe_kaggle/` 合并集 11,623 张图片、28,853 个框，按图片哈希去重并完成三类目标校验
- [x] `results/expanded_ppe_kaggle_validation_latest.json` 合并集 train/val/test 质量报告
- [x] `data/hard_cases/`、`data/hard_cases/hard_case_manifest.json` 和 `results/hard_cases_validation.json` 定向 hard-case 数据与校验
- [ ] 不把权重、数据库、上传文件和运行结果强制提交到源码仓库；交付时可按老师要求单独打包

## 可复现实验

- [x] `scripts/download_dataset.py`
- [x] `scripts/validate_dataset.py`
- [x] `scripts/train_yolo.py`
- [x] `scripts/evaluate_yolo.py`
- [x] `scripts/benchmark.py`
- [x] `results/baseline-n-smoke-metrics.json`
- [x] `results/baseline-s-smoke-metrics.json`
- [x] `results/expanded-ppe-yolov8s-smoke-metrics.json`（1 epoch GPU smoke baseline，已标注实验边界）
- [x] `results/expanded-ppe-yolov8s-5ep-test-metrics.json`（独立 test split 实测指标）
- [x] `results/expanded-ppe-yolov8s-finetune10-test-metrics.json`（旧扩充集对照版本独立 test split 实测指标）
- [x] `results/expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json`（合并集 8 epoch 独立 test split 实测指标）
- [x] `runs/train/expanded-ppe-yolov8s-kaggle-refine8/weights/best.pt`（E6 训练权重）
- [x] `results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`（E7 在基础合并集独立 test 上的实测指标）
- [x] `runs/train/expanded-ppe-yolov8s-hardcase12/weights/best.pt`（E7 训练权重，best epoch 7）
- [x] `scripts/evaluate_demo_set.py`、`data/hard_cases/regression_expectations.json` 和 `results/hardcase-regression-hardcase12.json`（三图硬性门禁）
- [x] `scripts/evaluate_video_cases.py` 和 `results/video-regression-hardcase12.json`（两视频短轨迹门禁）
- [x] `scripts/download_kaggle_dataset.py`、`docs/KAGGLE_DATA.md`（Kaggle 可选下载与审计）
- [x] E8 30 epoch 训练权重：`runs/train/expanded-ppe-yolov8s-e8-video150/weights/best.pt`
- [x] E8 权重 SHA256 与“不部署”决策：`results/e8-video150-gate-review.json`
- [x] E8 训练后自动门禁脚本：`scripts/run_e8_gate_after_training.ps1`
- [x] E8 test、hard-case、demo、video 四项验收产物已保存

## 功能验收

- [x] `/health` 返回 200
- [x] 登录返回 JWT
- [x] 图片上传返回检测 JSON 和预览图
- [x] 视频任务经历 queued/running/completed 或给出明确失败原因
- [x] 摄像头创建和危险区配置成功
- [x] 告警查询、确认、关闭成功
- [x] WebSocket token 鉴权、事件推送、ping/pong 成功
- [x] 浏览器首页、登录、图片、视频、摄像头、危险区、事件和指标区域可操作
- [x] 内置演示素材下拉加载图片/视频，避免现场手动查找路径
- [x] 任务中心可查看图片/视频任务历史、状态、进度和结果文件
- [x] 模型实验页可查看 YOLOv8n/YOLOv8s 实际指标与数据集质量校验
- [x] 模型实验页展示 E7 当前结果、E6 历史对照、旧 Expanded PPE 10/5 epoch 与 smoke，分项指标仅保留 person/helmet/vest

## 文档与展示

- [x] `docs/SETUP.md` 环境安装
- [x] `docs/API.md` 接口契约
- [x] `docs/DATABASE.md` 数据库设计
- [x] `docs/DATASET.md` 数据说明
- [x] `docs/SYSTEM_DESIGN.md` 系统设计
- [x] `docs/EXPERIMENTS.md` 实验记录
- [x] `docs/TEST_REPORT.md` 测试报告
- [x] `docs/USER_MANUAL.md` 用户手册
- [x] `docs/FRONTEND_VALIDATION.md` 前端校验
- [x] `docs/DEMO_GUIDE.md` 现场演示手册
- [x] `docs/PRESENTATION_SCRIPT.md` 答辩讲解稿
- [x] `docs/PPT_OUTLINE.md` PPT 大纲
- [x] 阶段性 Word 文档：`学号_姓名_工业安全智能监测系统_环境搭建与运行说明.docx`
- [x] 展示讲解 Word 手册：`学号_姓名_工业安全智能监测系统_展示讲解演示手册.docx`
- [x] E8 训练复核已写入 `docs/EXPERIMENTS.md`、`docs/TEST_REPORT.md` 和 `docs/DATASET.md`

## 最终诚实边界

当前已完成可运行工程、公开数据下载与校验、E7 12 epoch GPU 精调、E8 30 epoch 候选训练、基础合并集同口径 test、三图两视频定向回归、短轨迹过滤、接口与工作台；本机 CUDA 已验证。当前服务仍部署 E7，E8 未替换线上。3 张原图及 180 张增强、E8 的 150 张视频抽帧均不等于计划中的 300–500 帧独立自建集。80 epoch、正式 720p/15 FPS、独立自建样本定量测试和跟踪/规则消融仍需单独执行，不应在提交材料中写成已完成。
