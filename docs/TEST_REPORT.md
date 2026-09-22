# 测试报告

测试日期：2026-09-20

## 环境与被测版本

| 项目 | 实测状态 |
| --- | --- |
| Python | 3.12.13 |
| PyTorch / TorchVision | 2.6.0+cu126 / 0.21.0+cu126 |
| Ultralytics | 8.4.152 |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU，CUDA 可用 |
| 当前权重 | `models/expanded-ppe-yolov8s-hardcase12.pt` |
| 权重 SHA256 | `73CD31A09209C3F9B0375210160873B014F69F5FFF6B7B82EFA254C57D630E4F` |
| 基础独立 test | 1,163 张图片，3,047 个框；未挂载 hard-case |

## 自动化测试

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check app\static\app.js
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
```

结果：`49 passed`，2 条既有依赖弃用 warning；JavaScript 语法与 Python compileall 通过。

| 模块 | 覆盖内容 |
| --- | --- |
| Detector | fallback、坐标裁剪、人员/PPE 几何过滤、异常框过滤 |
| Tracker | track_id、3 次连续命中确认、遮挡后已确认轨迹保持、未确认人员的 PPE 隐藏 |
| Rules | PPE 关联、正负证据冲突、按轨迹观测次数计算宽限、3 帧确认、10 秒冷却、危险区边界 |
| API | health、JWT、图片推理、任务、事件、摄像头、危险区、指标、实验摘要、错误路径 |
| WebSocket | JWT 鉴权、事件推送、ping/pong |
| Frontend | 六页结构、关键控件、接口地址、静态资源 Content-Type |
| 回归工具 | 图片预期清单、视频关键帧断言、失败退出码和报告边界 |

## E7 训练与独立测试

E7 从 E6 权重继续训练 12 epoch，best epoch 为 7。训练时在基础 train 8,276 张/20,695 框上额外挂载 3 张用户抽查原图及 180 张增强，得到 8,459 张/21,732 框；val/test 保持基础合并集原划分。

| 指标 | 聚合 | person | helmet | vest |
| --- | ---: | ---: | ---: | ---: |
| Precision | 0.7977 | 0.8589 | 0.7323 | 0.8020 |
| Recall | 0.6620 | 0.7811 | 0.4548 | 0.7500 |
| F1 | 0.7235 | 0.8182 | 0.5611 | 0.7751 |
| mAP@0.5 | 0.7200 | 0.8267 | 0.5292 | 0.8040 |
| mAP@0.5:0.95 | 0.4441 | - | - | - |

证据：`results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`。同一 test split 的 E6 为 Precision 0.8332、Recall 0.6441、F1 0.7266、mAP@0.5 0.7151、mAP@0.5:0.95 0.4538、helmet Recall 0.4353。E7 提升了 Recall、mAP@0.5 和 helmet Recall，同时降低了 Precision 与 mAP@0.5:0.95；该取舍必须如实保留。

## 三张图片定向门禁

命令使用 `data/hard_cases/regression_expectations.json`，断言失败返回非零退出码。结果文件：`results/hardcase-regression-hardcase12.json`。

| 样本 | 检测结果 | 事件 | 结果 |
| --- | --- | --- | --- |
| 三人施工图 | 3 person、3 helmet、2 vest | `no_vest` | 通过；机械区域无 person |
| 工厂黑帽图 | 2 person、2 helmet、2 vest | 无 | 通过；黑色安全帽 0.7057，无 `no_helmet` |
| 施工通道图 | 1 person、1 helmet、1 vest | 无 | 通过 |

以上样本参与了定向训练，只能作为已知问题回归，不能用来计算独立 Precision、Recall 或 mAP。

## 两段视频定向门禁

结果文件：`results/video-regression-hardcase12.json`。脚本使用与服务一致的 3 次轨迹命中确认、3 帧事件确认、10 秒冷却和 15 次人员观测 PPE 宽限/预热。

| 视频 | 帧数 | 确认轨迹 | 事件 | 关键结论 |
| --- | ---: | ---: | --- | --- |
| `9dd0...mp4` | 239 | 1 | 无 | 单人 PPE 持续稳定 |
| `7894...mp4` | 712 | 3 | `no_vest`，按冷却间隔产生 | 第 198、475、476 帧均只有 3 名确认人员；机械短候选未进入输出、统计和规则 |

## 接口与前端验收

| 项目 | 验收标准 |
| --- | --- |
| `/health` | Ultralytics 后端、`model_available=true`、当前 E7 权重、输入 640 |
| 登录 | `admin/admin123` 返回 JWT，工作台解除登录遮罩 |
| 图片 | 返回结构化检测、事件、结果 JSON 和标注预览；前端优先展示标注图片而非原始 JSON |
| 视频 | 任务经历 queued/running/completed，结果摘要返回可播放媒体与统计 |
| 模型实验 | 显示 E7 当前模型、E6 历史对照和旧实验；分项只保留 person/helmet/vest |
| 响应式布局 | 桌面与移动视口无内容重叠，上传预览保持原图比例 |

## 最终 API 实测

2026-09-20 使用独立 8011 端口启动服务并完成真实请求，验证结束后已关闭临时服务。

| 场景 | 实测结果 |
| --- | --- |
| 健康检查 | 200；`backend=ultralytics`，`model_available=true`，模型为 E7，输入 640 |
| 登录与鉴权 | 正确账号返回 200 和 JWT；错误密码、无 Token 业务请求均返回 401 |
| 实验摘要 | 200；包含 `YOLOv8s (Expanded + Kaggle + hard cases, 12 epoch refine)` |
| 图片上传 | `hard_02.jpg` 在 1.963 秒内返回 2 person、2 helmet、2 vest、0 事件 |
| 图片结果 | 任务 completed/100%；标注 JPEG 返回 200、`image/jpeg`、44,093 bytes |
| 视频上传 | 239 帧视频返回 202，约 7.10 秒后 completed/100% |
| 视频结果 | 742 个确认检测、0 事件；WebM 返回 200、`video/webm`、3,606,533 bytes |

OpenCV 首次尝试 VP80 编码时输出容器 tag 警告，随后回退成功，结果媒体可访问，不影响任务完成。开发版 `/results/*` 由公开静态目录提供，适用于本机课程演示；公网部署前应改为鉴权下载或短时签名 URL。

## 仍未完成的正式实验

- 80 epoch 长周期训练。
- 300-500 帧按视频或人员划分的独立自建场景测试。
- 720p 端到端处理达到 15 FPS 的正式可复现实测。
- A1 无跟踪、A2 仅跟踪、A3 完整时间过滤与冷却的定量消融。

旧 E1-E6 指标、旧权重、数据库和证据文件均保留用于追溯。fallback 只用于接口流程演示；3 张 hard-case 及其 180 张增强不能冒充独立数据集。

## E8 训练完成后的最终门禁复核（2026-09-22）

E8 已完成 30/30 轮，最佳权重为
`runs/train/expanded-ppe-yolov8s-e8-video150/weights/best.pt`，SHA256 为
`FD853116D0ED24791B7F78E0195DDBAF540A9B62712105C2D59B5B4168EAFD42`。训练后按
`test → hard-case → demo → video` 顺序执行门禁，四项命令均返回 0：

| 门禁 | 结果文件 | 结果 |
| --- | --- | --- |
| 同口径 test 指标 | `results/expanded-ppe-yolov8s-e8-video150-test-metrics.json` | 通过 |
| 3 张 hard-case 断言 | `results/hardcase-regression-e8-video150.json` | 通过，`operational_errors=[]` |
| 8 张演示图流程 | `results/demo-regression-e8-video150.json` | 通过 |
| 2 段视频回归 | `results/video-regression-e8-video150.json` | 通过，`operational_errors=[]` |

E8 与当前 E7 在同一 test split 的聚合指标如下：

| 指标 | E7 | E8 | E8-E7 | 解释 |
| --- | ---: | ---: | ---: | --- |
| Precision | 0.7977 | 0.7803 | -0.0174 | 下降 |
| Recall | 0.6620 | 0.6732 | +0.0112 | 上升 |
| F1 | 0.7235 | 0.7228 | -0.0007 | 略降 |
| mAP@0.5 | 0.7200 | 0.7095 | -0.0105 | 下降 |
| mAP@0.5:0.95 | 0.4441 | 0.4463 | +0.0022 | 略升 |
| helmet Recall | 0.4548 | 0.4868 | +0.0320 | 上升 |

复核决策：继续部署 E7 `models/expanded-ppe-yolov8s-hardcase12.pt`，不自动替换为
E8。原因是 E8 虽改善召回类指标，但总体 Precision、F1 和 mAP@0.5 下降，且新增
视频帧不是独立人工标注测试集。完整决策记录见
`results/e8-video150-gate-review.json`。E8 只能作为候选实验权重保留，不能在展示中
声称为已验证的最终模型。
