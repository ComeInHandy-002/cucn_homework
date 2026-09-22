# 系统设计

## 总体架构

```text
Browser Workstation
        |
        v
FastAPI API  ---- SQLAlchemy ---- SQLite / PostgreSQL
        |
        v
Inference Service
        |
        +-- YOLOv8Detector / FallbackDetector
        +-- ByteTrack-like Tracker
        +-- PPE Association
        +-- Danger Zone Rule Engine
        +-- Evidence and Result Writer
```

## 核心流程

| 阶段 | 输入 | 处理 | 输出 |
| --- | --- | --- | --- |
| 上传 | 图片/视频文件 | 文件校验、保存到 `uploads/` | source_path |
| 检测 | frame | YOLOv8 或 fallback 推理 | Detection 列表 |
| 跟踪 | person 检测框 | IoU 匹配生成稳定 ID | track_id |
| PPE 关联 | person/helmet/vest | 判断 PPE 中心点与人体区域关系 | PPEAssociation |
| 危险区 | person + polygon | 用脚底中心点判断点在多边形内 | intrusion 事件候选 |
| 告警确认 | 连续帧候选 | 3 帧确认、10 秒冷却 | SafetyEvent |
| 持久化 | job/event/result | 写数据库与 `results/` | API 可查询结果 |

## 规则说明

- 安全帽：PPE 框中心点必须落在人员框内，且位于人员框上部 40% 区域。
- 反光背心：PPE 框中心点必须落在人员框内，且位于人员框 20%-85% 纵向区域。
- 危险区域：使用摄像头配置的多边形和人员框脚底中心点做越界判断。
- 视频告警：同一 `camera_id + track_id + event_type` 连续 3 帧成立才生成告警。
- 冷却去重：同一人员同一规则 10 秒内只保留一次告警。

## 工程边界

- 第一版不接入 RTSP，不控制真实设备，不做人脸识别或身份识别。
- 没有本地权重时，fallback 只用于接口和系统演示，不代表模型性能。
- 真实论文指标必须来自公开数据集和自建样本上的训练、验证、测试结果。
