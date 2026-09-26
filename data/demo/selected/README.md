# 答辩演示素材包

此目录中的文件可直接在系统“智能检测”页面上传。推荐先使用图片确认模型已加载，再提交短视频。

## 推荐顺序

1. `images/01_光伏作业_安全帽背心.jpeg`：首选图片，目标大且检测框清晰；当前权重实测识别 2 个 Person、1 个 helmet、1 个 vest。
2. `images/05_缺少安全帽_有背心.jpg`：违规对照，当前权重实测识别 Person 和 vest，但未识别到 helmet。
3. `images/06_双人场景_混合穿戴.jpg`：适合解释多人关联与 `track_id`。
4. `videos/01_工程师安全帽背心_合规.mp4`：首选视频，三名工程师的安全帽和反光背心清晰，适合完整跟踪演示。
5. `videos/02_施工人员缺安全帽_违规.mp4`：仅 5 秒，适合快速触发缺少安全帽规则；该素材来源仓库为 MIT 许可证，但仓库没有单独说明视频原始拍摄者，正式公开发布前应再次核实。
6. `videos/03_施工人员行走_跟踪.mp4`：单人移动约 10 秒，适合演示 ByteTrack 轨迹稳定性。
7. `videos/04_城市施工人员_PPE.mp4`：多人施工约 13 秒，适合 PPE 检测与遮挡场景。
8. `videos/05_混凝土作业_缺PPE.mp4`：近距离作业约 13 秒，当前权重抽样检测到 Person、未稳定检测到 helmet/vest，适合违规规则演示。

`素材总览.jpg` 可用于快速挑选。模型抽样结果只说明当前权重对这些素材的现场表现，不是测试集指标。

## 来源与许可

- 图片来自项目已归档的 Ultralytics Construction-PPE 测试集，详细来源、哈希和数据集许可见 `data/dataset_sources.json` 与 `docs/DATASET.md`。
- Mixkit 视频按 [Mixkit Free License](https://mixkit.co/license/#videoFree) 下载，可用于本地课程演示。
- Coverr 视频按 [Coverr License](https://coverr.co/license) 下载，可用于本地课程演示。
- PPE 测试视频来自 `Morteza-Asadi-Shalmaiy/PPE-Detection-YOLOv8`，仓库许可证为 MIT；视频素材未单列原作者信息，因此仅作为本地备用演示素材。

逐文件 URL、尺寸、时长和 SHA256 见 `manifest.json`。
