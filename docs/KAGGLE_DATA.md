# Kaggle 数据下载说明

## 结论

项目保留两条可复现路径：`scripts/prepare_sh17_expanded.py` 生成旧的
`data/expanded_ppe/`，而 Kaggle PPE Detection（句柄
`uzairahmad1434/ppe-detection`）经归一化后参与当前合并集
`data/expanded_ppe_kaggle/`。Kaggle 数据页的压缩包结构和版本可能变化，许可证仍以
数据页和原始数据提供者声明为准；下载、去重、类别映射和 SHA256 都记录在合并集清单。

## 快速使用

脚本不把 `kagglehub` 写入项目必装依赖。公开数据通常可以匿名下载；若 Kaggle 当前策略要求登录，按 Kaggle 官方提示配置令牌即可，项目本身不保存账号密钥。

先检查命令，不访问网络：

```powershell
.\.venv\Scripts\python.exe scripts\download_kaggle_dataset.py --dry-run
```

安装可选下载器并下载默认 SH17 Kaggle 数据集：

```powershell
uv pip install kagglehub
.\.venv\Scripts\python.exe scripts\download_kaggle_dataset.py
```

基础合并集和 E6 历史实验使用的 Kaggle PPE Detection 来源可显式指定：

```powershell
.\.venv\Scripts\python.exe scripts\download_kaggle_dataset.py `
  --dataset uzairahmad1434/ppe-detection `
  --output data\downloads\kaggle\ppe-detection `
  --normalize-yolo --normalized-output data\kaggle_ppe
```

默认下载位置为 `data/downloads/kaggle/sh17/`。脚本会写入 `kaggle_manifest.json`，其中包含数据集句柄、下载时间、数据格式、图片/标签数量、识别到的类别、元数据 SHA256 和许可证复核提醒。

如果下载目录包含 `data.yaml` 或 `dataset.yaml`，可以额外生成只包含三类目标的独立 YOLO 数据集：

```powershell
.\.venv\Scripts\python.exe scripts\download_kaggle_dataset.py `
  --normalize-yolo `
  --normalized-output data\kaggle_ppe
```

归一化类别固定为 `0 person`、`1 helmet`、`2 vest`。脚本只保留能映射到这三类的框，并记录被跳过的非法/其他类别框；输出的 `data/kaggle_ppe/dataset.yaml` 可直接用于 Ultralytics 训练。

## 与现有扩充集的关系

`data/kaggle_ppe/` 是 Kaggle 的独立归一化副本，`data/expanded_ppe_kaggle/` 是在旧
扩充集基础上按图片 SHA256 去重后的合并副本；两者都不会覆盖
`data/expanded_ppe/`。E6 使用该合并副本，E7 在其 train 之上额外挂载定向 hard-case；基础集校验结果为 train/val/test 8,276 /
2,184 / 1,163 张图片、20,695 / 5,111 / 3,047 个框，详见
`results/expanded_ppe_kaggle_validation_latest.json`。

如果重新下载或改用 Kaggle 版本，先执行质量校验：

```powershell
.\.venv\Scripts\python.exe scripts\validate_dataset.py `
  --dataset data\kaggle_ppe `
  --output results\kaggle_ppe_validation.json
```

确认来源目录后，可按图片哈希生成合并副本（不会改写来源目录）：

```powershell
.\.venv\Scripts\python.exe scripts\merge_ppe_datasets.py `
  --base data\expanded_ppe `
  --kaggle data\kaggle_ppe `
  --output data\expanded_ppe_kaggle

.\.venv\Scripts\python.exe scripts\validate_dataset.py `
  --dataset data\expanded_ppe_kaggle `
  --output results\expanded_ppe_kaggle_validation_latest.json
```

确认类别、图片和标签一一对应后，再单独训练并单独保存指标：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo.py `
  --data data\kaggle_ppe\dataset.yaml `
  --model models\yolov8s.pt `
  --workers 0 `
  --name kaggle-ppe-yolov8s
```

论文和答辩中需要明确数据来源是 Kaggle PPE Detection、Hugging Face 镜像还是二者合并，
并引用原始数据项目。E6/E7 的模型泛化指标只来自合并集独立 test split；不能把 Kaggle
页面指标、SH17 论文指标或 fallback 演示输出写成项目实测指标。

## 故障排查

| 现象 | 处理 |
| --- | --- |
| `缺少可选依赖 kagglehub` | 在当前虚拟环境执行 `uv pip install kagglehub`；不需要为不使用 Kaggle 的部署安装它 |
| Kaggle 返回登录/权限错误 | 检查数据页是否公开；按官方文档配置 token，不要把 `kaggle.json` 放入仓库 |
| 未发现 `data.yaml`/`dataset.yaml` | 该下载包不是 YOLO 导出，先核对数据页版本；当前归一化脚本不会猜测标签格式 |
| 找不到 person/helmet/vest | 检查 YAML 的 `names`；脚本只接受这些类别及常见同义名，避免把类别错映射进安全规则 |
| 数据量与文档不一致 | 以 `kaggle_manifest.json` 和校验报告中的实际数量为准，重新记录版本、时间和 SHA256 |
