# API 契约

基础地址：默认 `http://127.0.0.1:8000`；本机演示若使用 8010，则替换为
`http://127.0.0.1:8010`。除登录和健康检查外，接口默认需要
`Authorization: Bearer <token>`。

## 登录

`POST /api/v1/auth/login`

```json
{
  "username": "admin",
  "password": "admin123"
}
```

返回：

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": {"id": 1, "username": "admin", "role": "admin"}
}
```

## 图片推理

`POST /api/v1/inference/images`

表单字段：

- `file`: jpg/png/bmp/webp
- `camera_id`: 可选，用于加载该摄像头危险区域

返回 `InferenceResponse`，包含 `detections`、`events`、`result_path` 和 `preview_path`。

## 视频推理

`POST /api/v1/inference/videos`

表单字段：

- `file`: mp4/avi/mov/mkv
- `camera_id`: 可选

返回 202 和 `InferenceJob`。后台任务处理完成后，通过 `GET /api/v1/jobs/{job_id}` 查询状态。未安装 OpenCV 时任务会失败并返回明确错误信息。

## 推理任务中心

`GET /api/v1/jobs?status=completed&source_type=video&limit=50&offset=0`

返回当前用户可见的图片/视频推理任务，按创建时间倒序排列。`status` 可选：`queued`、`running`、`completed`、`failed`；`source_type` 可选：`image`、`video`。

`GET /api/v1/jobs/{job_id}/result`

返回任务的演示友好摘要：`preview_path`（标注图片或结果视频）、帧数、检测总数、按类别统计、按事件类型统计和最多 50 条事件。视频预览优先使用浏览器兼容的 WebM/VP8（无 VP8 编码器时回退 MP4）；任务中心默认打开这个摘要并展示媒体；`result_path` 仅作为“查看原始 JSON”的技术追溯入口，不再作为主要演示结果。

## 模型实验与数据质量

`GET /api/v1/experiments/summary`

返回项目已有实验产物和数据集质量校验结果：

- `models`：YOLOv8n、YOLOv8s 的 Precision、Recall、F1、mAP@0.5、mAP@0.5:0.95 及分项指标；当前服务实际加载的模型通过 `is_current=true` 标记；
- `splits`：train/val/test 图片数、标签数、标注框数和校验错误；
- `classes`：数据集类别清单。

接口优先读取合并集 `results/expanded_ppe_kaggle_validation_latest.json` 和
`data/expanded_ppe_kaggle/dataset_manifest.json` 展示规模；合并集不存在时回退到
旧 `results/expanded_ppe_validation.json` 与 `data/expanded_ppe/dataset_sources.json`。
模型指标读取实际生成的 `results/*-metrics.json`，当前包括 E7 hard-case 12 epoch 当前结果、E6 合并集 8 epoch 历史对照、旧扩充集 10/5 epoch 与 smoke 结果。E7 的友好名称为 `YOLOv8s (Expanded + Kaggle + hard cases, 12 epoch refine)`；其泛化指标仍来自基础合并集独立 test split。页面会标注训练轮数、数据版本、test split 与实验边界。

## 演示素材

`GET /api/v1/demo/assets`

登录后返回 `data/demo/selected/manifest.json` 中仍存在的本地图片和视频。返回项包含 `asset_id`、文件名、类型、尺寸/时长、SHA256 和可直接访问的 `/demo/...` URL。工作台的“载入样例”按钮使用该接口，不需要现场手动查找文件路径；素材目录只读挂载，路径会限制在演示素材根目录内。

## 告警事件

`GET /api/v1/events?status=open&event_type=no_helmet&limit=50&offset=0`

`PATCH /api/v1/events/{event_id}`

```json
{"status": "acknowledged"}
```

状态枚举：`open`、`acknowledged`、`resolved`。

## 摄像头与危险区域

`POST /api/v1/cameras`

```json
{
  "name": "车间A",
  "source": "local",
  "location": "一楼切割区",
  "enabled": true
}
```

`POST /api/v1/cameras/{camera_id}/zones`

```json
{
  "name": "主危险区",
  "enabled": true,
  "polygon": [{"x": 160, "y": 260}, {"x": 500, "y": 260}, {"x": 500, "y": 470}, {"x": 160, "y": 470}]
}
```

## 指标

`GET /api/v1/metrics/summary`

返回告警总数、待处理/已确认/已关闭数量、类型分布、等级分布、活跃摄像头数和今日任务数。

## WebSocket

`WS /api/v1/ws/events?token=<JWT>`

WebSocket 必须提供登录接口返回的 JWT。也可以在握手请求中使用 `Authorization: Bearer <JWT>`。连接成功后先返回：

```json
{"type":"connected","message":"Safety event websocket is ready"}
```

已有或新产生的事件会以如下结构推送：

```json
{"type":"event","event":{"id":"...","event_type":"no_helmet","status":"open"}}
```

客户端发送 `ping` 时返回 `{"type":"pong"}`。缺少或无效 token 时连接以 1008 关闭。

## 静态工作台

- `GET /`：返回浏览器工作台页面。
- `GET /static/styles.css`：样式表。
- `GET /static/app.js`：登录、图片/视频上传、摄像头/危险区、事件和指标交互逻辑。
- `GET /results/<filename>`：访问推理结果、预览图和证据截图。
- `GET /demo/<images|videos>/<filename>`：访问已归档的本地演示素材。
