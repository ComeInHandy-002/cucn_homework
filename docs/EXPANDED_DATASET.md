# 扩充数据集说明

## 结果

`data/expanded_ppe/` 是独立生成的三类 YOLO 数据集，原始 `data/external/construction-ppe/` 不会被覆盖。

| split | 图片 | 标注框 |
| --- | ---: | ---: |
| train | 6,802 | 17,731 |
| val | 1,762 | 4,318 |
| test | 951 | 2,667 |
| 合计 | 9,515 | 24,716 |

类别固定为：`0 person`、`1 helmet`、`2 vest`。

## 来源与许可证

- Construction-PPE：Ultralytics assets release，项目内保留原始压缩包、`LICENSE` 和 `data/dataset_sources.json`。使用前遵循数据包中的 AGPL-3.0/数据集声明。
- SH17：项目仓库 [ahmadmughees/SH17dataset](https://github.com/ahmadmughees/SH17dataset)，原项目 README 声明 CC BY-NC-SA 4.0；本次下载使用 [Hugging Face 镜像](https://huggingface.co/datasets/fathansanum/SH-17-Dataset)，镜像的导出说明另写 CC BY 4.0。论文或公开发布前应以原始数据提供者的许可为准，并保留来源和引用。

SH17 原始类别按项目论文/README 映射：`Person -> person`、`Helmet -> helmet`、`Safety-vest -> vest`。其他类别不写入扩充集。

## 复现

```powershell
.\.venv\Scripts\python.exe scripts\prepare_sh17_expanded.py --workers 12
.\.venv\Scripts\python.exe scripts\validate_dataset.py --dataset data\expanded_ppe --output results\expanded_ppe_validation.json
```

脚本具备断点跳过、失败重试和 HTTP 429 退避。原始 COCO 标注保存在 `data/downloads/sh17/`，扩充数据清单和标注 SHA256 保存在 `data/expanded_ppe/dataset_sources.json`。

## 重新训练

数据准备完成不等于模型指标提升。重新训练并评估：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo.py --data data/expanded_ppe/dataset.yaml --model yolov8s.pt --name expanded-ppe-yolov8s
.\.venv\Scripts\python.exe scripts\evaluate_yolo.py --weights runs/train/expanded-ppe-yolov8s/weights/best.pt --data data/expanded_ppe/dataset.yaml --output results/expanded-ppe-yolov8s-metrics.json
```

训练输出和指标必须与原始基线分开保存，不能将 SH17 论文中的指标直接写成本项目结果。

## Kaggle 合并实验副本

E6 及后续实验使用独立目录 `data/expanded_ppe_kaggle/`，在本页旧扩充集基础上加入
Kaggle PPE Detection，并按图片 SHA256 去重。实际规模为 train/val/test 8,276 /
2,184 / 1,163 张图片，20,695 / 5,111 / 3,047 个框；完整记录见
`data/expanded_ppe_kaggle/dataset_manifest.json` 与
`results/expanded_ppe_kaggle_validation_latest.json`。该副本不覆盖
`data/expanded_ppe/`。E6 使用基础合并集，是当前 E7 的历史对照；相关训练和 test 指标见 `docs/EXPERIMENTS.md`。

## E7 hard-case 挂载层

`data/expanded_ppe_hard.yaml` 不复制或改写基础合并集，而是在训练阶段额外挂载 `data/hard_cases/`。该目录包含 3 张用户抽查原图和每图 60 个确定性增强版本，共 183 张训练图、1,037 个框。有效训练输入为 8,459 张、21,732 个框；val/test 仍使用基础合并集的 2,184/1,163 张图片和 5,111/3,047 个框。

hard-case 没有独立 val/test，相关增强也不能算作独立真实场景。质量报告为 `results/hard_cases_validation.json`，清单为 `data/hard_cases/hard_case_manifest.json`；E7 独立泛化指标仍由基础合并集 test split 生成。
