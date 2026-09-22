# 文档索引

这是工业安全智能监测系统的文档入口，按阅读目的组织：

## 运行和使用

- [SETUP.md](SETUP.md)：Python、依赖、模型、GPU、Docker 环境搭建。
- [USER_MANUAL.md](USER_MANUAL.md)：普通用户操作手册和常见问题。
- [DEMO_GUIDE.md](DEMO_GUIDE.md)：5–8 分钟现场演示脚本、备用方案和故障处理。
- [FRONTEND_VALIDATION.md](FRONTEND_VALIDATION.md)：前端页面与接口映射、验收表。

## 系统设计

- [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)：总体架构、处理流程和规则。
- [DATABASE.md](DATABASE.md)：数据库表结构和字段说明。
- [API.md](API.md)：REST/WebSocket/静态资源接口契约。

## 数据和实验

- [DATASET.md](DATASET.md)：数据来源、许可证、划分和校验规则。
- [EXPANDED_DATASET.md](EXPANDED_DATASET.md)：Construction-PPE + SH17 扩充集构建、映射和质量报告。
- [KAGGLE_DATA.md](KAGGLE_DATA.md)：Kaggle 可选下载、审计、类别归一化和许可证边界。
- [EXPERIMENTS.md](EXPERIMENTS.md)：YOLOv8n/YOLOv8s 指标和消融实验计划。
- [TEST_REPORT.md](TEST_REPORT.md)：自动化、接口、视频和前端资源测试结果。

## 论文和答辩

- [PPT_OUTLINE.md](PPT_OUTLINE.md)：答辩 PPT 页面结构和证据对应关系。
- [PRESENTATION_SCRIPT.md](PRESENTATION_SCRIPT.md)：逐页讲解稿、90 秒项目介绍和问答。
- [THESIS_OUTLINE.md](THESIS_OUTLINE.md)：论文章节提纲。
- [DELIVERY_CHECKLIST.md](DELIVERY_CHECKLIST.md)：提交前源码、数据、模型、文档和验收清单。

## 结果文件

- `data/dataset_sources.json`：数据源和归档 SHA256。
- `results/dataset_validation.json`：数据集结构校验。
- `results/baseline-n-smoke-metrics.json`：YOLOv8n 1 epoch smoke baseline。
- `results/baseline-s-smoke-metrics.json`：YOLOv8s 1 epoch smoke baseline。
- `results/expanded-ppe-yolov8s-smoke-metrics.json`：Expanded PPE 1 epoch GPU smoke baseline。
- `results/expanded-ppe-yolov8s-finetune10-test-metrics.json`：旧 Expanded PPE 10 epoch GPU 对照的独立 test split 指标。
- `results/expanded-ppe-yolov8s-5ep-test-metrics.json`：Expanded PPE 5 epoch GPU 对照的独立 test split 指标。
- `results/expanded_ppe_kaggle_validation_latest.json`：Expanded PPE + Kaggle PPE 合并集的 train/val/test 质量校验。
- `results/expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json`：E6 历史部署的合并集 8 epoch GPU 精调独立 test 指标。
- `results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`：E7 当前部署模型在基础合并集独立 test 上的指标。
- `results/expanded-ppe-yolov8s-e8-video150-test-metrics.json`：E8 30 epoch 候选模型在同一 test split 的对照指标。
- `results/e8-video150-gate-review.json`：E8 四项门禁、指标差异、SHA256 和不部署决策。
- `results/e8-video150-gate-summary.json`：E8 训练后自动门禁命令汇总。
- `runs/train/expanded-ppe-yolov8s-hardcase12/weights/best.pt`：E7 训练权重（运行目录默认被 `.gitignore` 忽略）。
- `runs/train/expanded-ppe-yolov8s-e8-video150/weights/best.pt`：E8 候选训练权重，不是当前服务权重。
- `data/hard_cases/hard_case_manifest.json`、`results/hard_cases_validation.json`：3 张抽查原图及增强的清单与格式校验。
- `results/hardcase-regression-hardcase12.json`、`results/video-regression-hardcase12.json`：E7 三图两视频定向回归，不作为独立泛化指标。
- `docs/DIAGNOSTIC_RECHECK_2026-09-20.md`：E6 切换前问题诊断及 E7 修复后复核。

基础合并集规模为 train/val/test 8,276/2,184/1,163 张图片、20,695/5,111/3,047 个标注框。E7 训练额外挂载 183 张相关 hard-case 图和 1,037 个框，E8 另加 150 张 train-only 视频抽帧，val/test 均不变。当前服务仍为 E7；所有指标都来自实际运行，fallback、定向回归和 E8 补充帧都不可冒充独立模型指标。
