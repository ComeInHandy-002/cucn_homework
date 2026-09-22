# E6 切换前诊断与 E7 修复复核（2026-09-20）

前半部分保留 `kaggle-refine8` 切换前的原始诊断证据；文末追加 E7 新权重的独立测试与同一批样本复核。两组结果不能混写。

## 复核范围

- 默认权重：`models/expanded-ppe-yolov8s-kaggle-refine8.pt`
- SHA-256：`A78D65A51D79A06638B3A75830608036F92E750D650F6C76003FCF0A5F1EDCFC`
- 文件大小：22,503,971 bytes
- 推理环境：Ultralytics 8.4.152，PyTorch 2.6.0+cu126，NVIDIA GeForce RTX 4070 Laptop GPU
- 图片路径：
  - `uploads/adc6cc3e035f4948bf11d0b616bffaca.jpg`
  - `uploads/45e2ac329e5b480abfc5bec52ca4ca98.jpg`
  - `uploads/9d806c26de5b4602936b1567cf68469d.jpg`
- 视频路径：
  - `uploads/9dd0c7b9ae444314a01de70e3c3f5468.mp4`
  - `uploads/7894c9c171c6449194fcc8d5f0235cc4.mp4`

图片按当前服务路径使用 `strict_ppe=True`（YOLO TTA）；视频按服务路径使用普通单次推理。原始输出另以 `conf=0.001` 检查，用于区分模型漏检与后处理丢弃。

## 图片结果

| 文件 | 当前后处理输出 | 规则事件 | 结论 |
|---|---|---|---|
| `adc6...jpg`（1280×720） | 3 person、3 helmet、2 vest | `no_vest` track 2 | 三名工人和三顶帽子均保留；左侧黑衣工人没有反光背心，事件符合画面。原始输出另有背景机械弱 person（0.3017，`[157,370,292,473]`），被小目标过滤。 |
| `45e2...jpg`（640×640） | 1 person（0.5056）、1 vest（0.7101） | `no_helmet` track 1 | 工人实际戴黑色/深色安全帽，但模型没有在头部给出可用 helmet。TTA 原始最高 helmet 为 0.1384，且框为背景位置 `[441,233,468,259]`；真实头部仅有约 0.0035 的极弱候选，不是简单的关联丢失。 |
| `9d806...jpg`（640×360） | 1 person（0.8087）、1 helmet（0.2312）、1 vest（0.4839） | 无 | 该样本当前识别正常。 |

### 黑色安全帽样本的具体证据

`45e2...jpg` 的真实头部位于主体框上方中央。原始 TTA 输出中，覆盖真实头部的 helmet 候选最高仅约 `0.0035`；相对较高的 `0.1384` helmet 框位于右侧背景。将 helmet 阈值从 `0.15` 降到常规范围不能解决；若降到千分位，反而会引入大量背景框。这是训练数据/域泛化问题，应补充黑色帽、低对比度和室内样本后重新训练。

## 视频结果

| 视频 | 全帧统计 | 规则事件 | 备注 |
|---|---|---|---|
| `9dd0...mp4`（239 帧，23.98 FPS，640×360） | 1 个持续 person track；239 person、436 helmet、239 vest | 0 | PPE 输出在部分帧有重复 helmet 框（同一工人约 2 个候选），虽未触发告警，但说明 PPE 去重仍不稳定。 |
| `7894...mp4`（712 帧，25 FPS，640×360） | 3 个主 person track 持续全片；2139 person、2247 helmet、1433 vest | 第 17 帧 `no_vest` track 3 | 大多数帧为 3 person/3 helmet/2 vest，事件与左侧无背心工人一致。 |

### 视频中仍存在的机械误检

`7894...mp4` 中发现两个短暂的背景机械 person track：

| 帧 | track | 置信度 | 框（xyxy） | 现场判断 |
|---:|---:|---:|---|---|
| 198 | 4 | 0.6002 | `[74.1,172.4,123.4,220.2]` | 画面左侧红色挖掘机/机械，不是人员 |
| 475 | 5 | 0.4654 | `[103.6,129.3,149.7,205.5]` | 画面左侧挖掘机/机械，不是人员 |
| 476 | 5 | 0.4986 | `[102.4,129.3,150.3,204.9]` | 同上 |

可视证据帧：

- `results/_diagnostic_recheck/7894_frame_198.jpg`
- `results/_diagnostic_recheck/7894_frame_475.jpg`
- `results/_diagnostic_recheck/7894_frame_476.jpg`

当前 `_is_tiny_ambiguous_person()` 仅在置信度 `< 0.60` 时检查小目标。第 198 帧的 `0.6002` 刚好绕过该边界；第 475–476 帧虽然置信度较低，但框高约 75 px、宽高比约 1.6，未满足现有几何过滤条件。它们没有连续达到 3 帧，因此本次没有升级成安全事件，但会污染检测框和 track 统计。

## 结论与修复优先级

1. **黑色安全帽漏检是模型能力问题**：真实头部只有约 `0.0035` 的极弱候选，不能靠前端或单纯调阈值修复。应加入黑色/深色帽、室内低照度、遮挡和小目标 hard-case，至少进行 20–40 epoch 继续训练，并用独立测试集检查 helmet recall。
2. **机械误检是后处理边界 + 训练负样本共同问题**：建议将上述视频帧加入 hard-negative 回归集，并在规则层禁止短暂背景框进入人员统计；任何阈值调整都要重新测量真实远距离工人的召回率。
3. **重复 helmet 框需要独立统计**：在视频评估中记录每帧每人的 PPE 候选数量，避免把重复框误解为多个安全帽或影响关联稳定性。
4. 新权重切换前必须重新运行本报告中的五个样本/视频，并保留原始输出、后处理输出和事件结果，不能只看单张可视化截图。

## E7 修复后复核

- 部署权重：`models/expanded-ppe-yolov8s-hardcase12.pt`
- SHA256：`73CD31A09209C3F9B0375210160873B014F69F5FFF6B7B82EFA254C57D630E4F`
- 训练：从 E6 继续精调 12 epoch，best epoch 7；3 张抽查原图及 180 张增强只挂载到 train。
- 独立 test：`results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`，Precision 0.7977、Recall 0.6620、F1 0.7235、mAP@0.5 0.7200、mAP@0.5:0.95 0.4441；helmet Recall 0.4548。

### 三张原图门禁

`results/hardcase-regression-hardcase12.json` 的全部断言通过：

| 文件 | 检测计数 | 事件 | 复核结论 |
| --- | --- | --- | --- |
| `adc6...jpg` / `hard_01.jpg` | 3 person、3 helmet、2 vest | `no_vest` | 机械区域无 person；只对实际无背心人员告警 |
| `45e2...jpg` / `hard_02.jpg` | 2 person、2 helmet、2 vest | 无 | 主体黑色安全帽置信度 0.7057；旧 `no_helmet` 误告警消失 |
| `9d806...jpg` / `hard_03.jpg` | 1 person、1 helmet、1 vest | 无 | 通道样本保持正确 |

### 两段视频门禁

`results/video-regression-hardcase12.json` 的全部断言通过：

- `9dd0...mp4`：239 帧，1 条确认人员轨迹，无事件。
- `7894...mp4`：712 帧，3 条确认人员轨迹；第 198、475、476 帧确认人员数均为 3，机械的 1–2 帧候选未进入确认输出、统计或规则。
- 无背心人员按 10 秒冷却产生 `no_vest`，未出现机械触发的 PPE 告警。

这些三图两视频结果是定向回归，不是独立泛化指标。E7 与 E6 的同 test split 对比显示 Recall、mAP@0.5 和 helmet Recall 提升，Precision 与 mAP@0.5:0.95 下降；论文中必须保留这一真实取舍。
