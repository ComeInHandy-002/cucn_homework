# 前端工作台校验说明

## 页面入口

启动服务后打开实际监听地址，例如 `http://127.0.0.1:8010/`。页面由 `app/static/index.html`、`styles.css` 和 `app.js` 组成，不依赖单独的 Node 构建流程。

## 页面功能与接口映射

| 页面区域 | 操作 | 调用接口 | 验收标准 |
| --- | --- | --- | --- |
| 顶部健康状态 | 页面加载 | `GET /health` | 状态徽章显示后端、模型是否可用 |
| 登录 | 输入账号密码并提交 | `POST /api/v1/auth/login` | 登录遮罩关闭，侧栏显示用户角色，token 写入 localStorage |
| 监控总览 | 登录后自动刷新 | `GET /api/v1/metrics/summary`、`GET /api/v1/events`、`GET /api/v1/cameras` | 指标卡、告警环图/等级条、实时事件和监控点状态出现数据 |
| 图片检测 | 拖拽/选择图片、绑定监控点、上传 | `POST /api/v1/inference/images` | 检测画面、目标分类计数、结构化明细、事件判定和 JSON 同步更新 |
| 图片/视频示例 | 在下拉框选择并载入内置素材 | `GET /api/v1/demo/assets`、`GET /demo/...` | 文件自动放入上传框，显示文件名/大小，可直接提交 |
| 视频任务 | 选择 MP4、绑定监控点、提交 | `POST /api/v1/inference/videos`、`GET /api/v1/jobs/{id}` | 显示 queued/running/completed、进度条和结果链接 |
| 任务中心 | 按状态/类型筛选历史任务 | `GET /api/v1/jobs` | 显示图片/视频任务、进度、失败信息和结果文件 |
| 模型实验 | 查看模型对比和数据质量 | `GET /api/v1/experiments/summary` | 显示 E7 当前模型（表格标记“当前部署”）、E8 video150 30 epoch 候选、E6 合并集历史对照、旧集 10/5 epoch 与 smoke、分项指标和 train/val/test 校验结果 |
| 摄像头 | 填名称/source/location 新增 | `POST /api/v1/cameras`、`GET /api/v1/cameras` | 设备卡片、总览监控点和全部下拉框同步刷新 |
| 危险区 | 在画布点击顶点或编辑坐标 JSON | `POST /api/v1/cameras/{id}/zones` | 多边形预览、撤销/清空、保存成功后规则引擎可使用该区域 |
| 告警事件 | 按状态/类型筛选，查看证据、确认、关闭 | `GET /api/v1/events`、`PATCH /api/v1/events/{id}` | 表格状态、告警数量和总览卡片同步更新 |
| 实时事件 | 登录后自动建立连接 | `WS /api/v1/ws/events?token=<JWT>` | 顶部实时通道在线，收到事件时弹出提示并插入告警列表 |

## 已执行校验

- `GET /`、`/static/styles.css`、`/static/app.js`：静态资源路由已注册。
- `GET /api/v1/demo/assets` 与 `/demo/...`：内置图片/视频样例清单和只读文件路由已校验。
- 登录、图片上传、事件查询/更新、摄像头、危险区、指标接口：自动化测试通过。
- WebSocket JWT 鉴权、已有事件推送、心跳：自动化测试通过。
- 真实演示图片：当前 E7 权重完成 8 张内置样例回归，明细见 `results/demo-regression-hardcase12.json`；E8 候选的 8 张回归见 `results/demo-regression-e8-video150.json`；三张抽查原图硬性门禁见 `results/hardcase-regression-hardcase12.json`。
- 短 MP4：上传返回 202，后台任务完成并生成结果 JSON。
- JavaScript 可通过浏览器直接加载；没有 Node 构建产物或外部 CDN 依赖。
- 模型实验接口已包含 E7 当前模型友好名称、E8 候选友好名称、E6 历史对照、旧 Expanded PPE 10/5 epoch 与 smoke 结果，以及合并集 3 个 split 的校验结果。真实端口 8010 的最终浏览器验收以本文后续记录为准。
- 真实运行端口 8010 的静态资源响应头已校验：HTML 为 `text/html`、CSS 为 `text/css`、JS 为 `text/javascript`。如果 8000 被其他应用占用，必须使用实际启动端口访问。

## 人工浏览器验收表

在现场按下表逐项打勾，截图可作为展示证据：

| 序号 | 操作 | 预期画面 | 结果 |
| --- | --- | --- | --- |
| 1 | 打开首页 | 顶部显示系统名和健康状态 | □ |
| 2 | 使用 `admin/admin123` 登录 | 登录状态显示 `admin · admin` | □ |
| 3 | 选择 `data/external/construction-ppe/images/test/image1.jpeg` | 文件名显示在选择框 | □ |
| 3a | 图片检测页选择内置样例并点击“载入图片样例” | 文件名、大小和预览图自动出现 | □ |
| 4 | 点击“上传并检测” | 预览图和 JSON 出现 | □ |
| 5 | 新增摄像头 | 摄像头列表出现新项，下拉框同步 | □ |
| 6 | 保存危险区 | 表单提交无报错 | □ |
| 7 | 刷新告警 | 表格显示时间、类型、等级、状态 | □ |
| 8 | 点击确认/关闭 | 状态更新为 acknowledged/resolved | □ |
| 9 | 提交短 MP4 | 任务经历 queued/running/completed | □ |
| 9a | 视频检测页选择内置样例并点击“载入视频样例” | 视频文件名和大小自动出现 | □ |
| 10 | 刷新指标 | 数字与事件/任务变化一致 | □ |
| 11 | 图片检测完成后回到监控总览 | 最近检测画面卡片显示缩略图，可跳回检测中心 | □ |
| 12 | 打开任务中心 | 历史任务、状态筛选、进度和结果链接出现 | □ |
| 13 | 打开模型实验 | E7 行显示“当前部署”，E8 显示为 30 epoch candidate 且不带当前标签；分项指标标题与 E7 一致，同时出现 E6 历史对照、旧 Expanded PPE 10/5 epoch、smoke 和数据质量校验 | □ |

## 界面实现边界

- 当前为无需构建步骤的单页工作台，使用侧栏切换“监控总览、智能检测、任务中心、模型实验、告警中心、设备与区域”六个页面。
- 危险区域支持 720×405 画布点选、撤销、清空；JSON 文本框作为精确坐标和兼容接口的高级输入。
- 前端会在登录后自动连接 WebSocket；断线后约 3.5 秒重连，顶部状态徽章反映实时通道状态。
- 图表使用本地 CSS/SVG 绘制，不依赖 CDN；页面在窄屏下自动折叠侧栏并适配移动布局。已用 CDP 390×844 移动视口复核登录层，卡片、输入框和按钮均保持在可视区域内；证据截图：`results/frontend-mobile-cdp-after.png`。
- 后端返回的本地路径由前端转换为 `/results/` URL；部署到反向代理时需保持该静态目录映射。
