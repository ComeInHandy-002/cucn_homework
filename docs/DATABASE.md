# 数据库设计

默认开发环境使用 SQLite：`sqlite:///./safety_monitor.db`。Docker Compose 使用 PostgreSQL。

## users

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 主键 |
| username | string | 登录名，唯一 |
| password_hash | string | PBKDF2 哈希 |
| role | string | `admin` 或 `operator` |
| is_active | boolean | 是否启用 |
| created_at | datetime | 创建时间 |

## cameras

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 主键 |
| name | string | 摄像头名称 |
| source | string | 本地设备、文件路径或预留 RTSP 地址 |
| location | string | 安装位置 |
| enabled | boolean | 是否启用 |
| created_at | datetime | 创建时间 |

## danger_zones

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 主键 |
| camera_id | integer | 外键，关联 cameras |
| name | string | 危险区名称 |
| polygon | json | 点数组，如 `[{"x":160,"y":260}]` |
| enabled | boolean | 是否启用 |
| created_at | datetime | 创建时间 |

## inference_jobs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | UUID 主键 |
| source_type | string | `image` / `video` / `camera` |
| source_path | string | 上传文件路径 |
| status | string | `queued` / `running` / `completed` / `failed` |
| progress | float | 0-100 |
| result_path | string | 结果 JSON 路径 |
| error_message | text | 失败原因 |
| camera_id | string | 可选摄像头 ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## safety_events

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | UUID 主键 |
| event_type | string | `no_helmet` / `no_vest` / `intrusion` |
| severity | string | `medium` / `high` / `critical` |
| camera_id | string | 摄像头 ID |
| track_id | integer | 跟踪 ID |
| timestamp | datetime | 事件时间 |
| evidence_path | string | 证据截图路径 |
| status | string | `open` / `acknowledged` / `resolved` |
| zone_id | string | 危险区 ID |
| message | string | 事件描述 |
| metadata | json | 规则上下文 |
