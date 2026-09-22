# 答辩 PPT 大纲

1. 题目页
2. 研究背景：工业作业安全与人工巡检问题
3. 项目目标：PPE 检测、危险区域入侵、告警闭环
4. 系统架构：FastAPI、推理服务、数据库、前端工作台
5. 算法流程：YOLOv8 检测、ByteTrack 跟踪、PPE 关联、规则判断
6. 数据集与标注：公开数据集、自建样本、类别定义、划分策略
7. 模型实验：Construction-PPE 基线、Expanded PPE 1 epoch smoke、旧扩充集 5/10 epoch、E6 8 epoch 与 E7/E8 同口径 test split 对比，明确 E7 当前部署、E8 30 epoch 候选及数据边界
8. 消融实验：无跟踪、无时间过滤、完整方案对比
9. 系统实现：接口、任务、告警、危险区配置
10. 演示流程：健康检查、登录、图片检测、摄像头/危险区、告警处理、视频任务、指标查看
11. 测试结果：自动化测试、接口验收、异常处理
12. 总结与展望

注意：E7 12 epoch、E8 30 epoch 候选、E6 8 epoch 和旧集 10/5 epoch 指标来自对应记录的 test split，可作为工程对照；E8 不替换 E7。3 张 hard-case 原图及增强、E8 150 张视频抽帧只用于定向修复或训练补充。80 epoch、正式 720p 性能、300–500 帧独立自建样本和消融尚未完成时必须标注“未执行”，不能用计划值替代。

## 演示材料对应关系

| PPT 页 | 现场证据 |
| --- | --- |
| 4–5 系统与算法 | `docs/SYSTEM_DESIGN.md`、`app/core/` |
| 6 数据集 | `data/expanded_ppe_kaggle/dataset_manifest.json`、`results/expanded_ppe_kaggle_validation_latest.json` |
| 7 模型实验 | `results/baseline-n-smoke-metrics.json`、`results/baseline-s-smoke-metrics.json`、`results/expanded-ppe-yolov8s-smoke-metrics.json`、`results/expanded-ppe-yolov8s-5ep-test-metrics.json`、`results/expanded-ppe-yolov8s-finetune10-test-metrics.json`、`results/expanded-ppe-yolov8s-kaggle-refine8-test-metrics.json`、`results/expanded-ppe-yolov8s-hardcase12-test-metrics.json`、`results/expanded-ppe-yolov8s-e8-video150-test-metrics.json`、`results/e8-video150-gate-review.json` |
| 9–10 系统实现与演示 | `docs/API.md`、`docs/DEMO_GUIDE.md` |
| 11 测试 | `docs/TEST_REPORT.md`、`docs/FRONTEND_VALIDATION.md` |
