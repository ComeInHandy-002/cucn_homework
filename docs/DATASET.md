# 数据集记录模板

本项目使用公开 PPE 数据集，并计划补充 300-500 帧独立自建场景样本。当前已加入 3 张用户抽查原图作为定向 hard-case 训练补充；所有数据必须保留来源、版本、许可证和标注类别记录。

## 数据来源表

| 数据集 | 来源链接 | 版本/下载日期 | 许可证 | 类别 | 用途 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| Construction-PPE | [Ultralytics assets](https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip) | 2025-09 release；本地下载记录见 `data/dataset_sources.json` | 随包 AGPL-3.0 声明 | helmet, gloves, vest, boots, goggles, none, Person, no_helmet, no_goggle, no_gloves, no_boots | train/val/test | 公开预训练数据；论文指标必须由本项目实际训练生成 |
| SH17 | [项目仓库](https://github.com/ahmadmughees/SH17dataset) / [Kaggle 数据页](https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection) | 8,099 张；本地镜像与 COCO 标注见 `data/downloads/sh17/` | SH17 项目声明 CC BY-NC-SA 4.0；镜像 README 另声明 CC BY 4.0，公开发布前需复核 | Person, Helmet, Safety-vest 映射为 person, helmet, vest | 扩充训练/验证/测试 | 仅保留系统需要的三类，其他 PPE 类别不混入规则引擎 |
| 定向 hard-case | 用户上传的 3 张工业场景原图 | 2026-09-20；清单见 `data/hard_cases/hard_case_manifest.json` | 仅用于本项目验证，不对外再分发 | person, helmet, vest | train/定向回归 | 原图及增强仅用于修复已知问题，不做人脸识别，不作为独立泛化测试 |
| 计划自建场景集 | 本地采集 | 未完成 | 自有 | person, helmet, vest | 独立 test/demo | 仍需采集 300-500 帧并按视频或人员划分 |

## 划分规则

- 按视频或人员划分 train/val/test，避免相邻帧同时进入训练集和测试集。
- 自建样本优先覆盖车间光照、遮挡、远距离、小目标和危险区域边界。
- 标注统一转换为 YOLO 格式：`class x_center y_center width height`，坐标归一化到 0-1。
- 类别建议固定为：`0 person`、`1 helmet`、`2 vest`。

## 目录建议

```text
data/
  raw/
  interim/
  yolo/
    images/train
    images/val
    images/test
    labels/train
    labels/val
    labels/test
  dataset.yaml
```

## 质量检查

- 随机抽查每个 split 的图片和标签是否一一对应。
- 检查类别 id 是否越界。
- 检查标注框是否超出图像边界。
- 对测试集保留原始视频/采集批次信息，便于论文解释泛化能力。

## 当前下载状态

`data/external/construction-ppe/` 已包含 1132 张 train、143 张 val、141 张 test 图片及对应 YOLO 标签。压缩包大小、SHA256、下载时间和许可证记录在 `data/dataset_sources.json`。该公开数据集包含 11 个类别；系统运行时的 `helmet`、`vest`、`Person` 和 `no_helmet` 等类别由检测器类别归一化逻辑处理，其余类别可用于模型训练但不触发安全规则。

## 扩充数据集

已生成独立的 `data/expanded_ppe/`，不会覆盖原始基线。该目录将 Construction-PPE 和 SH17 统一为三类：`0 person`、`1 helmet`、`2 vest`。

| split | 图片数 | 标注框 | 空标签图片 |
| --- | ---: | ---: | ---: |
| train | 6,802 | 17,731 | 162 |
| val | 1,762 | 4,318 | 39 |
| test | 951 | 2,667 | 17 |

数据清单、原始标注 SHA256 和类别映射见 `data/expanded_ppe/dataset_sources.json`；质量报告见 `results/expanded_ppe_validation.json`。复现下载、转换和合并步骤：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_sh17_expanded.py --workers 12
.\.venv\Scripts\python.exe scripts\validate_dataset.py --dataset data\expanded_ppe --output results\expanded_ppe_validation.json
```

扩充数据只代表数据准备完成，不代表模型指标已经提升。重新训练后，必须使用独立测试集重新生成 Precision、Recall、F1 和 mAP。

## Kaggle 合并集（当前主实验）

`data/expanded_ppe_kaggle/` 是独立生成的合并副本：在 `data/expanded_ppe/` 基础
上加入 Kaggle `uzairahmad1434/ppe-detection`，按图片 SHA256 去重，不修改任一来源
目录。类别仍固定为 `0 person`、`1 helmet`、`2 vest`。

| split | 图片数 | 标注框 | 空标签图片 |
| --- | ---: | ---: | ---: |
| train | 8,276 | 20,695 | 651 |
| val | 2,184 | 5,111 | 181 |
| test | 1,163 | 3,047 | 86 |

合计 11,623 张图片、28,853 个框。重复哈希、来源和处理时间见
`data/expanded_ppe_kaggle/dataset_manifest.json`，质量校验见
`results/expanded_ppe_kaggle_validation_latest.json`。E6 8 epoch 使用该基础合并集，作为历史对照。

## 定向 hard-case 训练补充

`scripts/prepare_hard_cases.py` 从 3 张用户抽查原图生成每图 60 个确定性增强版本。加上原图共 183 张训练图、1,037 个标注框；`data/expanded_ppe_hard.yaml` 只把它们挂载到 train，val/test 仍使用合并集原划分。有效训练输入为 8,459 张、21,732 个框，独立 val/test 仍分别为 2,184 张/5,111 框和 1,163 张/3,047 框。

格式校验见 `results/hard_cases_validation.json`，三张原图的定向门禁见 `results/hardcase-regression-hardcase12.json`。183 张衍生图高度相关，不能表述为 183 个独立真实场景，也不能用其回归结果代替 Precision、Recall 或 mAP；E7 的独立 test 指标来自未挂载 hard-case 的 `data/expanded_ppe_kaggle` test split，见 `results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`。

## E8 视频帧补充（仅 train）

E8 训练目录额外加入 150 张视频抽帧，其中 132 张为伪正样本、18 张为
hard-negative。补充数据只写入 E8 的 train 配置，不改变基础合并集的 val/test；没有
为这些帧建立独立人工标注的测试划分。因此 E8 报告中的 1,163 张/3,047 框 test
指标仍来自 `data/expanded_ppe_kaggle` 原 test split，适合 E7/E8 同口径比较，但不能
包装成无泄漏泛化评估。来源、生成方式和门禁边界记录在
`results/e8-video150-gate-review.json`，E8 训练权重 SHA256 为
`FD853116D0ED24791B7F78E0195DDBAF540A9B62712105C2D59B5B4168EAFD42`。
