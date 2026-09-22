# 实验设计

不要在没有真实训练和测试的情况下填写模型指标。当前文档用于记录可复现实验配置和结果。

## 基线实验

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | FPS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | YOLOv8n | 320 | 1 | Construction-PPE release 2025-09 | 0.6844 | 0.3074 | 0.4242 | 0.2970 | 0.1421 | CPU smoke baseline |
| E2 | YOLOv8s | 320 | 1 | Construction-PPE release 2025-09 | 0.7545 | 0.3208 | 0.4502 | 0.3771 | 0.1748 | CPU smoke baseline |

## E2 基线分项指标（业务三类）

| 类别 | Precision | Recall | F1 | AP@0.5 | 典型误检 |
| --- | --- | --- | --- | --- | --- |
| person | 0.612 | 0.737 | 0.667 | 0.665 | 小目标、遮挡 |
| helmet | 0.849 | 0.763 | 0.804 | 0.836 | 远距离小目标 |
| vest | 0.917 | 0.562 | 0.698 | 0.778 | 遮挡和反光 |

上表取自 `results/baseline-s-smoke-metrics.json`，只列出规则层使用的
`person / helmet / vest`，并非合并集 E6/E7 的分项结果；后续实验分项结果见本页对应段落。

## 消融实验

| 方案 | 跟踪 | 时间过滤 | 冷却去重 | 误报变化 | 漏报变化 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 无 | 无 | 无 | 未执行 | 未执行 | 单帧检测规则 |
| A2 | 有 | 无 | 无 | 未执行 | 未执行 | 加稳定 track_id |
| A3 | 有 | 有 | 有 | 未执行 | 未执行 | 完整方案 |

## 验收目标

- 720p 视频在本地 NVIDIA GPU 上可演示实时处理，目标不低于 15 FPS。
- 单张图片接口返回检测结果和结构化 JSON。
- 告警事件包含可回看的证据截图。
- 训练参数、数据版本和模型权重路径可追溯。

## 已执行实验

指标由 `scripts/evaluate_yolo.py` 在 test split 实际运行生成，原始 JSON 保存在 `results/baseline-n-smoke-metrics.json` 和 `results/baseline-s-smoke-metrics.json`。两组均为 1 epoch、320 px、CPU smoke baseline，用于验证训练/评估链路，不代表 80 epoch 毕设最终指标。完整训练可将 `scripts/train_yolo.py` 的 `--epochs` 调整为 80，并在 GPU 环境执行。

## 扩充集 GPU 冒烟实验

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E3 | YOLOv8s | 320 | 1 | Expanded PPE（Construction-PPE + SH17） | 0.5904 | 0.3218 | 0.4166 | 0.3200 | 0.1507 | NVIDIA RTX 4070 Laptop GPU，GPU smoke baseline |

原始结果保存在 `results/expanded-ppe-yolov8s-smoke-metrics.json`，训练权重为 `runs/train/expanded-ppe-yolov8s-smoke/weights/best.pt`。E3 只用于验证扩充数据、CUDA 推理和评估链路，不能替代正式 80 epoch 训练，也不能据此声称达到 15 FPS。

扩充集分项 mAP@0.5 为：person 0.4647、helmet 0.1909、vest 0.3045。helmet 的召回率仅 0.1297，说明正式训练前仍需增加训练轮数、检查小目标增强和补充困难样本；页面会如实展示该结果，不做精度美化。

## 5 epoch GPU 训练与独立测试

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E4 | YOLOv8s | 640 | 5 | Expanded PPE（Construction-PPE + SH17） | 0.7705 | 0.5297 | 0.6278 | 0.5939 | 0.3596 | RTX 4070 Laptop GPU，test split |

E4 的原始结果保存在 `results/expanded-ppe-yolov8s-5ep-test-metrics.json`，权重为 `runs/train/expanded-ppe-yolov8s-5ep/weights/best.pt`，部署副本保留在 `models/expanded-ppe-yolov8s-5ep.pt`。分项 mAP@0.5 为：person 0.7736、helmet 0.3272、vest 0.6810。E4 作为可复现对照，不等同于论文中计划的 80 epoch 最终模型。

## 10 epoch GPU 微调与独立测试（旧扩充集对照版本）

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E5 | YOLOv8s | 640 | 10 | Expanded PPE（Construction-PPE + SH17） | 0.8361 | 0.5876 | 0.6902 | 0.6616 | 0.4075 | RTX 4070 Laptop GPU，独立 test split |

E5 的原始结果保存在 `results/expanded-ppe-yolov8s-finetune10-test-metrics.json`，训练权重为 `runs/train/expanded-ppe-yolov8s-finetune10/weights/best.pt`，部署副本仍保留在 `models/expanded-ppe-yolov8s-finetune10.pt`。分项 mAP@0.5 为：person 0.8027、helmet 0.3897、vest 0.7924。E5 仅作为旧扩充集对照，仍需在论文中明确训练轮数和 test split，不能包装成 80 epoch 最终模型。

## Expanded PPE + Kaggle PPE 合并集精调与独立测试

合并集先按图片 SHA256 去重，再统一为 `person / helmet / vest` 三类。校验报告
`results/expanded_ppe_kaggle_validation_latest.json` 给出的实际规模为：train 8,276
张、20,695 框；val 2,184 张、5,111 框；test 1,163 张、3,047 框（合计 11,623
张、28,853 框）。该报告同时保留重复哈希和空标签记录，不能把合并集数量与旧
Expanded PPE 的 9,515 张混用。

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | 说明 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| E6 | YOLOv8s | 640 | 8（从 refine12 权重继续精调） | Expanded PPE + Kaggle PPE | 0.8332 | 0.6441 | 0.7266 | 0.7151 | 0.4538 | RTX 4070 Laptop GPU，历史部署对照，独立 test split |

E6 的训练权重为 `runs/train/expanded-ppe-yolov8s-kaggle-refine8/weights/best.pt`，
独立测试结果为 `results/expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json`。
分项 Precision / Recall / F1 / mAP@0.5 为：person 0.8570 / 0.7713 / 0.8119 /
0.8196，helmet 0.7972 / 0.4353 / 0.5631 / 0.5135，vest 0.8456 / 0.7258 /
0.7811 / 0.8123。E6 是从旧扩充集 refine12 权重继续训练 8 个 epoch 的历史部署模型（副本：
`models/expanded-ppe-yolov8s-kaggle-refine8.pt`），用于与 E7 同一独立 test split 对照。它是 8 epoch 精调，不应写成 80 epoch 最终模型。

复现实验命令（Windows）：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo.py `
  --model runs\train\expanded-ppe-yolov8s-refine12\weights\best.pt `
  --data data\expanded_ppe_kaggle\dataset.yaml `
  --epochs 8 --imgsz 640 --batch 16 --device 0 --workers 0 `
  --optimizer AdamW --lr0 0.0001 --lrf 0.2 `
  --warmup-epochs 0 --close-mosaic 3 --patience 8 `
  --name expanded-ppe-yolov8s-kaggle-refine8

.\.venv\Scripts\python.exe scripts\evaluate_yolo.py `
  --weights runs\train\expanded-ppe-yolov8s-kaggle-refine8\weights\best.pt `
  --data data\expanded_ppe_kaggle\dataset.yaml --split test `
  --imgsz 640 --device 0 `
  --output results\expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json
```

E6 与 E5/E4 的 test split 不同，不能直接把两个数据集的指标当成严格的同集
对照；比较时应同时注明数据版本、划分和训练轮数。

## E7 定向 hard-case 精调与独立测试

E7 从 E6 权重继续训练，在基础 train 8,276 张/20,695 框之外挂载 3 张用户抽查原图及 180 张确定性增强图。有效训练输入为 8,459 张、21,732 框；val/test 完全沿用基础合并集，分别为 2,184 张/5,111 框和 1,163 张/3,047 框。hard-case 数据没有 val/test，不能把 183 张相关衍生图当成独立场景。

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | 说明 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| E7 | YOLOv8s | 640 | 12（best epoch 7） | Expanded PPE + Kaggle PPE + targeted hard cases | 0.7977 | 0.6620 | 0.7235 | 0.7200 | 0.4441 | RTX 4070 Laptop GPU，当前部署；独立 test 使用基础合并集原 test split |

E7 分项 Precision / Recall / F1 / mAP@0.5 为：person 0.8589 / 0.7811 / 0.8182 / 0.8267，helmet 0.7323 / 0.4548 / 0.5611 / 0.5292，vest 0.8020 / 0.7500 / 0.7751 / 0.8040。与同一 test split 的 E6 相比，E7 的 Recall、mAP@0.5 和 helmet Recall 上升，Precision 与 mAP@0.5:0.95 有所下降；这是定向修复后的真实取舍，不做单向美化。

训练权重为 `runs/train/expanded-ppe-yolov8s-hardcase12/weights/best.pt`，部署副本为 `models/expanded-ppe-yolov8s-hardcase12.pt`，SHA256 为 `73CD31A09209C3F9B0375210160873B014F69F5FFF6B7B82EFA254C57D630E4F`。独立指标见 `results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`。三张原图与两段视频的定向回归分别见 `results/hardcase-regression-hardcase12.json` 和 `results/video-regression-hardcase12.json`，两者都不是独立泛化指标。

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo.py `
  --data data\expanded_ppe_hard.yaml `
  --model models\expanded-ppe-yolov8s-kaggle-refine8.pt `
  --epochs 12 --imgsz 640 --batch 16 --device 0 --workers 0 `
  --cache none --optimizer AdamW --lr0 0.00005 --lrf 0.2 `
  --warmup-epochs 0 --close-mosaic 3 --patience 6 `
  --name expanded-ppe-yolov8s-hardcase12

.\.venv\Scripts\python.exe scripts\evaluate_yolo.py `
  --weights runs\train\expanded-ppe-yolov8s-hardcase12\weights\best.pt `
  --data data\expanded_ppe_kaggle\dataset.yaml --split test `
  --imgsz 640 --device 0 `
  --output results\expanded-ppe-yolov8s-hardcase12-test-metrics.json

.\.venv\Scripts\python.exe scripts\evaluate_demo_set.py `
  --weights runs\train\expanded-ppe-yolov8s-hardcase12\weights\best.pt `
  --images data\hard_cases\images\train --pattern "hard_??.jpg" `
  --expectations data\hard_cases\regression_expectations.json `
  --output results\hardcase-regression-hardcase12.json
```

E7 是当前工程部署结果，不等于计划中的 80 epoch 长周期实验。300–500 帧独立自建场景测试、正式 720p 端到端性能验收和 A1/A2/A3 消融仍应单独执行并保留原始结果。

## E8 视频帧补充训练与门禁复核

E8 在 E7/E6 路线基础上继续训练 30 个 epoch，训练目录为
`runs/train/expanded-ppe-yolov8s-e8-video150/`，最佳权重为
`runs/train/expanded-ppe-yolov8s-e8-video150/weights/best.pt`。本轮只向 train
增加 150 张视频抽帧：132 张伪正样本和 18 张 hard-negative。它们不是独立人工标注
的验证/测试场景，不能把这 150 张写成新的独立测试集。

| 实验 | 模型 | 输入尺寸 | epoch | 数据版本 | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 | helmet Recall | 结论 |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| E8 | YOLOv8s | 640 | 30 | E7 + 150 train-only video frames | 0.7803 | 0.6732 | 0.7228 | 0.7095 | 0.4463 | 0.4868 | 保留为候选，不替换 E7 |

E8 与 E7 使用同一 `data/expanded_ppe_kaggle` test split（1,163 张图片、3,047 个框）
复核：Recall、helmet Recall 和 mAP@0.5:0.95 上升，但 Precision、F1 和 mAP@0.5
下降。因此当前服务继续使用 E7，不根据单项指标切换模型。三张 hard-case、八张演示图和
两段视频门禁均通过，门禁只证明已知样本和流程没有运行错误，不等于独立泛化指标。

完整复核结论、SHA256 和产物路径见 `results/e8-video150-gate-review.json`；自动门禁汇总见
`results/e8-video150-gate-summary.json`。E8 权重不复制到 `models/`，以避免误部署。
