const state = {
  token: localStorage.getItem("safety_token") || "",
  user: JSON.parse(localStorage.getItem("safety_user") || "null"),
  cameras: [],
  demoAssets: [],
  events: [],
  jobs: [],
  zones: [],
  experimentSummary: null,
  eventStatus: "",
  eventType: "",
  socket: null,
  socketTimer: null,
  socketPing: null,
  zonePoints: [],
};

const ZONE_CANVAS_W = 720;
const ZONE_CANVAS_H = 405;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const EVENT_TYPES = {
  no_helmet: { label: "未佩戴安全帽", icon: "帽" },
  no_vest: { label: "未穿反光背心", icon: "服" },
  intrusion: { label: "危险区域闯入", icon: "界" },
};
const SEVERITY_LABELS = { critical: "严重", high: "高危", medium: "中危", low: "低危" };
const STATUS_LABELS = { open: "待处理", acknowledged: "已确认", resolved: "已关闭" };
const CLASS_LABELS = {
  person: "人员",
  helmet: "安全帽",
  hardhat: "安全帽",
  hard_hat: "安全帽",
  safety_helmet: "安全帽",
  vest: "反光背心",
  safety_vest: "反光背心",
  reflective_vest: "反光背心",
};
const PAGE_META = {
  overview: ["监控总览", "OPERATION CENTER"],
  detection: ["智能检测", "AI INFERENCE"],
  jobs: ["任务中心", "INFERENCE JOBS"],
  experiments: ["模型实验", "MODEL & DATA LAB"],
  alerts: ["告警中心", "SAFETY EVENTS"],
  configuration: ["设备与区域", "SYSTEM CONFIGURATION"],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function authHeaders(extra = {}) {
  return state.token ? { ...extra, Authorization: `Bearer ${state.token}` } : extra;
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: authHeaders(options.headers || {}) });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const error = new Error(data?.detail || data || response.statusText || "请求失败");
    error.status = response.status;
    throw error;
  }
  return data;
}

function pathToUrl(path) {
  if (!path) return "";
  const normalized = String(path).replaceAll("\\", "/");
  const markerIndex = normalized.lastIndexOf("/results/");
  if (markerIndex >= 0) return normalized.slice(markerIndex);
  if (normalized.startsWith("results/")) return `/${normalized}`;
  return normalized;
}

function showToast(title, message, type = "info", duration = 4200) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const symbols = { info: "i", success: "✓", warning: "!", error: "×" };
  toast.innerHTML = `<span>${symbols[type] || "i"}</span><div><strong></strong><p></p></div><button type="button">×</button>`;
  toast.querySelector("strong").textContent = title;
  toast.querySelector("p").textContent = message;
  toast.querySelector("button").addEventListener("click", () => toast.remove());
  $("#toastStack").append(toast);
  setTimeout(() => toast.remove(), duration);
}

function formatDateTime(value) {
  if (!value) return ["--:--:--", "----/--/--"];
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return ["--:--:--", "----/--/--"];
  return [
    date.toLocaleTimeString("zh-CN", { hour12: false }),
    date.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }),
  ];
}

function updateClock() {
  const [time, date] = formatDateTime(new Date());
  $("#currentTime").textContent = time;
  $("#currentDate").textContent = date;
}

function showPage(pageName) {
  if (!PAGE_META[pageName]) return;
  $$('[data-page-panel]').forEach((panel) => panel.classList.toggle("active", panel.dataset.pagePanel === pageName));
  $$('.nav-item[data-page]').forEach((button) => button.classList.toggle("active", button.dataset.page === pageName));
  $("#pageTitle").textContent = PAGE_META[pageName][0];
  $("#pageEyebrow").textContent = PAGE_META[pageName][1];
  $("#sidebar").classList.remove("open");
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (pageName === "configuration") requestAnimationFrame(drawZoneCanvas);
  if (pageName === "jobs" && state.token) refreshJobs().catch((error) => showToast("任务加载失败", error.message, "error"));
  if (pageName === "experiments" && state.token) refreshExperiments().catch((error) => showToast("实验数据加载失败", error.message, "error"));
}

function setAuthenticatedUser(user) {
  state.user = user || state.user;
  if (!state.user) return;
  $("#sidebarUsername").textContent = state.user.username || "用户";
  $("#sidebarRole").textContent = state.user.role === "admin" ? "系统管理员" : state.user.role || "普通用户";
}

function logout(showMessage = true) {
  state.token = "";
  state.user = null;
  localStorage.removeItem("safety_token");
  localStorage.removeItem("safety_user");
  disconnectWebSocket();
  $("#loginOverlay").classList.remove("hidden");
  $("#sidebarUsername").textContent = "管理员";
  $("#sidebarRole").textContent = "等待登录";
  if (showMessage) showToast("已退出系统", "登录令牌已从当前浏览器清除。", "info");
}

function renderMetrics(data) {
  $('[data-metric="total"]').textContent = data.total_events ?? 0;
  $('[data-metric="open"]').textContent = data.open_events ?? 0;
  $('[data-metric="cameras"]').textContent = data.active_cameras ?? 0;
  $('[data-metric="jobs"]').textContent = data.jobs_today ?? 0;
  $("#navAlertCount").textContent = data.open_events ?? 0;
  $("#eventDelta").textContent = data.total_events ? `已闭环 ${data.resolved_events ?? 0} 条事件` : "当前暂无安全告警";

  const types = data.events_by_type || {};
  const noHelmet = Number(types.no_helmet || 0);
  const noVest = Number(types.no_vest || 0);
  const intrusion = Number(types.intrusion || 0);
  const total = Math.max(Number(data.total_events || 0), noHelmet + noVest + intrusion);
  $("#donutTotal").textContent = total;
  $("#helmetEventCount").textContent = noHelmet;
  $("#vestEventCount").textContent = noVest;
  $("#intrusionEventCount").textContent = intrusion;
  if (total > 0) {
    const helmetEnd = (noHelmet / total) * 100;
    const vestEnd = helmetEnd + (noVest / total) * 100;
    $("#eventDonut").style.background = `conic-gradient(#ef476f 0 ${helmetEnd}%, #f59e0b ${helmetEnd}% ${vestEnd}%, #1477ff ${vestEnd}% 100%)`;
  } else {
    $("#eventDonut").style.background = "conic-gradient(#dce5ee 0 100%)";
  }

  const severity = data.events_by_severity || {};
  ["critical", "high", "medium", "low"].forEach((level) => {
    const count = Number(severity[level] || 0);
    $(`#${level}Count`).textContent = count;
    $(`#${level}Bar`).style.width = total ? `${Math.max((count / total) * 100, count ? 4 : 0)}%` : "0%";
  });
}

function createCameraOptions(select) {
  const previous = select.value;
  select.replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "未绑定监控点";
  select.append(empty);
  state.cameras.forEach((camera) => {
    const option = document.createElement("option");
    option.value = camera.id;
    option.textContent = camera.name;
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function renderCameraSelects() {
  [$("#imageCamera"), $("#videoCamera"), $("#zoneCamera")].forEach(createCameraOptions);
}

function renderDemoAssetOptions() {
  const groups = { image: $("#imageDemoAsset"), video: $("#videoDemoAsset") };
  Object.entries(groups).forEach(([sourceType, select]) => {
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "选择内置演示素材";
    select.append(empty);
    state.demoAssets.filter((asset) => asset.source_type === sourceType).forEach((asset) => {
      const option = document.createElement("option");
      option.value = asset.asset_id;
      const detail = asset.size ? ` · ${asset.size}` : "";
      option.textContent = `${asset.name}${detail}`;
      select.append(option);
    });
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  });
}

function renderCameras() {
  $("#cameraCountTag").textContent = `${state.cameras.length} 个设备`;
  if (!state.cameras.length) {
    $("#cameraList").innerHTML = '<div class="empty-state compact"><span>⌁</span><p>暂无监控点配置</p></div>';
    $("#overviewCameraList").innerHTML = '<div class="empty-state compact"><span>⌁</span><p>暂无摄像头</p></div>';
    return;
  }
  $("#cameraList").innerHTML = state.cameras.map((camera) => `
    <div class="camera-item">
      <div class="camera-item-icon">◉</div>
      <div><strong>${escapeHtml(camera.name)}</strong><span>${escapeHtml(camera.location || camera.source || "local")}</span></div>
      <div class="camera-state">● ${camera.enabled ? "运行中" : "已停用"}</div>
    </div>`).join("");
  $("#overviewCameraList").innerHTML = state.cameras.slice(0, 4).map((camera) => `
    <div class="camera-preview-card"><strong>${escapeHtml(camera.name)}</strong><span>${escapeHtml(camera.location || camera.source || "本地视频源")}</span></div>`).join("");
}

function renderRecentEvents() {
  const target = $("#recentEvents");
  if (!state.events.length) {
    target.innerHTML = '<div class="empty-state compact"><span>◎</span><p>暂无安全事件</p></div>';
    return;
  }
  target.innerHTML = state.events.slice(0, 4).map((event) => {
    const type = EVENT_TYPES[event.event_type] || { label: event.event_type, icon: "!" };
    const [time, date] = formatDateTime(event.timestamp);
    return `<div class="event-feed-item"><div class="event-symbol">${escapeHtml(type.icon)}</div><div><strong>${escapeHtml(type.label)}</strong><span>${escapeHtml(event.message || `监控点 ${event.camera_id || "未绑定"} · Track ${event.track_id ?? "--"}`)}</span></div><time>${date}<br>${time}</time></div>`;
  }).join("");
}

function renderEvents() {
  const body = $("#eventsBody");
  $("#eventTableInfo").textContent = `共 ${state.events.length} 条安全事件`;
  if (!state.events.length) {
    body.innerHTML = '<tr><td colspan="7" class="table-empty">当前筛选条件下暂无安全事件</td></tr>';
    renderRecentEvents();
    return;
  }
  body.innerHTML = state.events.map((event) => {
    const type = EVENT_TYPES[event.event_type] || { label: event.event_type, icon: "!" };
    const severity = String(event.severity || "medium");
    const status = String(event.status || "open");
    const [time, date] = formatDateTime(event.timestamp);
    const evidence = event.evidence_path ? `<button class="evidence-button" type="button" data-evidence="${escapeHtml(event.id)}">查看截图</button>` : '<span class="no-evidence">暂无证据</span>';
    const actions = status === "resolved" ? '<span class="no-evidence">已闭环</span>' : `<div class="actions">${status === "open" ? `<button type="button" data-event="${escapeHtml(event.id)}" data-status="acknowledged">确认</button>` : ""}<button type="button" data-event="${escapeHtml(event.id)}" data-status="resolved">关闭</button></div>`;
    return `<tr>
      <td><strong>${time}</strong><br><span class="no-evidence">${date}</span></td>
      <td><div class="event-name"><span class="event-name-icon">${escapeHtml(type.icon)}</span><div><strong>${escapeHtml(type.label)}</strong><span>${escapeHtml(event.message || "安全规则触发")}</span></div></div></td>
      <td>${escapeHtml(cameraName(event.camera_id))}<br><span class="no-evidence">Track ID: ${escapeHtml(event.track_id ?? "--")}</span></td>
      <td><span class="risk-badge ${escapeHtml(severity)}">${escapeHtml(SEVERITY_LABELS[severity] || severity)}</span></td>
      <td><span class="status-badge ${escapeHtml(status)}">${escapeHtml(STATUS_LABELS[status] || status)}</span></td>
      <td>${evidence}</td><td>${actions}</td>
    </tr>`;
  }).join("");
  renderRecentEvents();
}

const JOB_STATUS_LABELS = { queued: "排队中", running: "执行中", completed: "已完成", failed: "失败" };
const JOB_SOURCE_LABELS = { image: "图片", video: "视频" };

function jobResultTypeLabel(value) {
  return JOB_SOURCE_LABELS[String(value || "")] || "推理任务";
}

function isVideoPreview(path) {
  return /\.(mp4|webm|ogv)(?:\?|$)/i.test(String(path || ""));
}

function renderJobResultSummary(data) {
  const detections = data.detections_by_class || {};
  const events = data.events_by_type || {};
  const detectionTotal = Number(data.detection_count || 0);
  const eventTotal = Number(data.event_count || 0);
  const stats = [
    ["检测目标", detectionTotal],
    ["人员", detections.person || 0],
    ["安全帽", detections.helmet || 0],
    ["反光背心", detections.vest || 0],
  ];
  $("#jobResultSummary").innerHTML = stats.map(([label, value]) => `<div class="job-result-stat"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("") + `<p class="job-result-note">${jobResultTypeLabel(data.source_type)} · ${data.frames ? `${data.frames} 帧` : "单帧图片"} · ${eventTotal ? `发现 ${eventTotal} 条安全事件` : "未发现安全事件"}</p>`;
  if (!eventTotal) {
    $("#jobResultEvents").innerHTML = '<div class="result-alert"><span>✓</span><div><strong>本次未发现安全事件</strong><p>检测结果已生成，可继续查看标注媒体。</p></div></div>';
    return;
  }
  const labels = { no_helmet: "未佩戴安全帽", no_vest: "未穿反光背心", intrusion: "危险区域闯入" };
  $("#jobResultEvents").innerHTML = Object.entries(events).map(([type, count]) => `<div class="job-result-event"><strong>${escapeHtml(labels[type] || type)} · ${escapeHtml(count)} 条</strong><span>已记录证据，可在告警中心继续确认或关闭。</span></div>`).join("");
}

async function showJobResult(jobId) {
  const data = await api(`/api/v1/jobs/${encodeURIComponent(jobId)}/result`);
  $("#jobResultTitle").textContent = `${jobResultTypeLabel(data.source_type)}任务结果 · ${String(data.job_id || jobId).slice(0, 8)}`;
  $("#jobResultJson").href = pathToUrl(data.result_path);
  const preview = pathToUrl(data.preview_path);
  const previewBox = $("#jobResultPreview");
  if (preview) {
    if (isVideoPreview(data.preview_path)) {
      previewBox.innerHTML = `<video controls preload="metadata" src="${escapeHtml(preview)}"></video>`;
    } else {
      previewBox.innerHTML = `<img src="${escapeHtml(preview)}" alt="推理标注结果" />`;
    }
  } else {
    previewBox.innerHTML = '<div class="empty-state compact"><span>◌</span><p>该任务没有可视化媒体，仅保留结构化结果。</p></div>';
  }
  const media = $("#jobResultMedia");
  if (preview) {
    media.href = preview;
    media.textContent = isVideoPreview(data.preview_path) ? "打开结果视频" : "打开标注图片";
    media.classList.remove("hidden");
  } else {
    media.classList.add("hidden");
  }
  renderJobResultSummary(data);
  $("#jobResultModal").classList.remove("hidden");
}

function renderJobs() {
  const jobs = state.jobs || [];
  const counts = jobs.reduce((result, job) => {
    result.total += 1;
    if (["queued", "running"].includes(job.status)) result.running += 1;
    if (job.status === "completed") result.completed += 1;
    if (job.status === "failed") result.failed += 1;
    return result;
  }, { total: 0, running: 0, completed: 0, failed: 0 });
  $("#jobTotal").textContent = counts.total;
  $("#jobRunning").textContent = counts.running;
  $("#jobCompleted").textContent = counts.completed;
  $("#jobFailed").textContent = counts.failed;
  $("#jobTableInfo").textContent = `共 ${jobs.length} 条任务`;
  if (!jobs.length) {
    $("#jobsBody").innerHTML = '<tr><td colspan="6" class="table-empty">当前筛选条件下暂无任务记录</td></tr>';
    return;
  }
  $("#jobsBody").innerHTML = jobs.map((job) => {
    const [time, date] = formatDateTime(job.created_at);
    const status = String(job.status || "queued");
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    const result = job.result_path ? `<button class="text-button job-result-button" type="button" data-job-result="${escapeHtml(job.job_id)}">查看可视化结果</button>` : (job.error_message ? `<span class="no-evidence" title="${escapeHtml(job.error_message)}">错误详情</span>` : '<span class="no-evidence">处理中</span>');
    return `<tr><td><strong>${time}</strong><br><span class="no-evidence">${date}</span></td><td>${escapeHtml(JOB_SOURCE_LABELS[job.source_type] || job.source_type || "未知")}</td><td><code class="job-id">${escapeHtml(job.job_id)}</code></td><td><span class="status-badge ${escapeHtml(status)}">${escapeHtml(JOB_STATUS_LABELS[status] || status)}</span></td><td><div class="job-progress"><i style="width:${progress}%"></i></div><small>${progress.toFixed(1)}%</small></td><td>${result}</td></tr>`;
  }).join("");
}

async function refreshJobs() {
  if (!state.token) return;
  const query = new URLSearchParams({ limit: "100" });
  const status = $("#jobStatusFilter")?.value;
  const source = $("#jobSourceFilter")?.value;
  if (status) query.set("status", status);
  if (source) query.set("source_type", source);
  state.jobs = await api(`/api/v1/jobs?${query.toString()}`);
  renderJobs();
}

function formatMetric(value) {
  return value === null || value === undefined ? "--" : Number(value).toFixed(3);
}

function renderExperiments(summary) {
  state.experimentSummary = summary;
  $("#experimentDatasetName").textContent = summary.dataset_name || "Expanded PPE";
  const version = summary.dataset_version ? new Date(summary.dataset_version).toLocaleDateString("zh-CN") : "版本未记录";
  $("#experimentDatasetVersion").textContent = `数据记录 ${version}`;
  $("#experimentClassCount").textContent = (summary.classes || []).length;
  const splits = summary.splits || {};
  ["train", "val", "test"].forEach((split) => { $(`#${split}ImageCount`).textContent = splits?.[split]?.images ?? 0; });
  $("#experimentTotalImages").textContent = ["train", "val", "test"].reduce((total, split) => total + Number(splits?.[split]?.images || 0), 0);
  $("#experimentTotalBoxes").textContent = ["train", "val", "test"].reduce((total, split) => total + Number(splits?.[split]?.boxes || 0), 0);
  const models = summary.models || [];
  $("#experimentModelsBody").innerHTML = models.length ? models.map((model) => `<tr class="${model.is_current ? "current-model-row" : ""}"><td><strong>${escapeHtml(model.model_name)}</strong>${model.is_current ? '<span class="current-model-tag">当前部署</span>' : ""}<br><span class="no-evidence">${escapeHtml(model.dataset_name || "未记录数据版本")}</span><br><span class="no-evidence">${escapeHtml(model.weights || "")}</span></td><td>${formatMetric(model.precision)}</td><td>${formatMetric(model.recall)}</td><td>${formatMetric(model.f1)}</td><td>${formatMetric(model.map50)}</td><td>${formatMetric(model.map50_95)}</td></tr>`).join("") : '<tr><td colspan="6" class="table-empty">扩充集尚未生成训练指标</td></tr>';
  $("#experimentNotes").textContent = summary.notes || "指标来自项目实际评估结果。";
  $("#experimentSplits").innerHTML = ["train", "val", "test"].map((name) => {
    const split = splits[name] || {};
    const errors = split.errors?.length || 0;
    return `<div class="split-row"><div><strong>${name.toUpperCase()}</strong><span>${split.images ?? 0} 张图片 · ${split.labels ?? 0} 个标签 · ${split.boxes ?? 0} 个框</span></div><b class="${errors ? "quality-error" : "quality-ok"}">${errors ? `${errors} 个问题` : "校验通过"}</b></div>`;
  }).join("");
  const preferred = models.find((model) => model.is_current)
    || models.find((model) => String(model.model_name || "").toLowerCase().includes("hard cases"))
    || models.find((model) => (model.dataset_name || "").startsWith("Expanded PPE"))
    || models.find((model) => model.model_name === "YOLOv8s")
    || models[0];
  $("#classMetricsTitle").textContent = preferred?.is_current ? "E7 当前部署分项指标" : (preferred ? `${preferred.model_name} 分项指标` : "模型分项指标");
  $("#classMetricsSplitTag").textContent = preferred?.is_current ? "当前部署 · test split" : "test split";
  const perClass = Object.entries(preferred?.per_class || {});
  $("#classMetricsBody").innerHTML = perClass.length ? perClass.map(([name, metric]) => `<tr><td><strong>${escapeHtml(CLASS_LABELS[name] || name)}</strong><br><span class="no-evidence">${escapeHtml(name)}</span></td><td>${formatMetric(metric.precision)}</td><td>${formatMetric(metric.recall)}</td><td>${formatMetric(metric.f1)}</td><td>${formatMetric(metric.map50)}</td></tr>`).join("") : '<tr><td colspan="5" class="table-empty">暂无分项指标</td></tr>';
}

async function refreshExperiments() {
  if (!state.token) return;
  renderExperiments(await api("/api/v1/experiments/summary"));
}

function cameraName(cameraId) {
  if (cameraId === null || cameraId === undefined) return "未绑定监控点";
  return state.cameras.find((camera) => String(camera.id) === String(cameraId))?.name || `监控点 ${cameraId}`;
}

function classKey(name) {
  return String(name || "unknown").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
}

function classCategory(name) {
  const key = classKey(name);
  if (["person", "worker", "people"].includes(key)) return "person";
  if (["helmet", "hardhat", "hard_hat", "safety_helmet"].includes(key)) return "helmet";
  if (["vest", "safety_vest", "reflective_vest"].includes(key)) return "vest";
  return "other";
}

function renderImageResult(data) {
  const detections = Array.isArray(data.detections) ? data.detections : [];
  const events = Array.isArray(data.events) ? data.events : [];
  const counts = { person: 0, helmet: 0, vest: 0 };
  detections.forEach((detection) => {
    const category = classCategory(detection.class_name);
    if (category in counts) counts[category] += 1;
  });
  $("#detectionTotal").textContent = detections.length;
  $("#personCount").textContent = counts.person;
  $("#helmetCount").textContent = counts.helmet;
  $("#vestCount").textContent = counts.vest;
  $("#imageState").className = "state-chip success";
  $("#imageState").textContent = "检测完成";
  $("#detectionBody").innerHTML = detections.length ? detections.map((detection) => {
    const key = classKey(detection.class_name);
    const label = CLASS_LABELS[key] || detection.class_name;
    return `<tr><td><div class="class-cell"><span class="class-icon">◉</span>${escapeHtml(label)}</div></td><td><span class="confidence">${(Number(detection.confidence || 0) * 100).toFixed(1)}%</span></td><td>${escapeHtml(detection.track_id ?? "--")}</td></tr>`;
  }).join("") : '<tr><td colspan="3" class="table-empty">当前图片未检测到目标</td></tr>';
  const resultAlert = $("#resultAlert");
  if (events.length) {
    resultAlert.classList.add("has-alerts");
    resultAlert.innerHTML = `<span>!</span><div><strong>发现 ${events.length} 条安全事件</strong><p>${escapeHtml(events.map((event) => EVENT_TYPES[event.event_type]?.label || event.event_type).join("、"))}</p></div>`;
  } else {
    resultAlert.classList.remove("has-alerts");
    resultAlert.innerHTML = "<span>✓</span><div><strong>未发现已确认安全事件</strong><p>检测结果已完成结构化分析。</p></div>";
  }
  $("#imageResult").textContent = JSON.stringify(data, null, 2);
}

function updateOverviewSnapshot(path, label = "图片检测结果") {
  const url = pathToUrl(path);
  if (!url) return;
  const card = $("#overviewSnapshot");
  $("#overviewSnapshotImage").src = url;
  $("#overviewSnapshotLabel").textContent = label;
  card.classList.remove("hidden");
}

async function refreshHealth() {
  const healthBox = $("#health");
  try {
    const health = await api("/health");
    healthBox.className = "status-pill online";
    healthBox.querySelector("span").textContent = `${health.status === "ok" ? "服务正常" : health.status} · ${health.detector_backend}`;
    $("#detectorBackend").textContent = health.detector_backend || "unknown";
    if (health.model_available) {
      const modelPath = String(health.model_path || "").split(/[\\/]/).pop() || "已加载权重";
      const size = health.image_size ? ` · ${health.image_size}px` : "";
      $("#modelStatus").textContent = `${modelPath}${size}`;
    } else {
      $("#modelStatus").textContent = `模型不可用${health.model_error ? `：${health.model_error}` : ""}`;
    }
  } catch (error) {
    healthBox.className = "status-pill error";
    healthBox.querySelector("span").textContent = "推理服务异常";
    $("#modelStatus").textContent = error.message;
  }
}

async function refreshMetrics() {
  if (!state.token) return;
  renderMetrics(await api("/api/v1/metrics/summary"));
}

async function refreshCameras() {
  if (!state.token) return;
  state.cameras = await api("/api/v1/cameras");
  renderCameraSelects();
  renderCameras();
}

async function refreshZones() {
  if (!state.token) return;
  state.zones = await api("/api/v1/zones");
  renderZones();
}

function renderZones() {
  const target = $("#zoneList");
  if (!target) return;
  $("#zoneCountTag").textContent = `${state.zones.length} 个区域`;
  if (!state.zones.length) {
    target.innerHTML = '<div class="empty-state compact"><span>◌</span><p>暂无危险区域</p></div>';
    return;
  }
  target.innerHTML = state.zones.map((zone) => `
    <div class="camera-item">
      <div class="camera-item-icon">⬠</div>
      <div><strong>${escapeHtml(zone.name)}</strong><span>${escapeHtml(cameraName(zone.camera_id))} · ${zone.polygon?.length ?? 0} 个顶点 · ${zone.coordinate_space === "relative" ? "相对坐标" : "像素坐标"}</span></div>
      <div class="zone-item-actions"><button type="button" class="text-button" data-zone-load="${escapeHtml(zone.id)}">载入画布</button><button type="button" class="icon-text-button danger-text" data-zone-delete="${escapeHtml(zone.id)}">删除</button></div>
    </div>`).join("");
}

async function refreshDemoAssets() {
  if (!state.token) return;
  state.demoAssets = await api("/api/v1/demo/assets");
  renderDemoAssetOptions();
}

async function refreshEvents() {
  if (!state.token) return;
  const query = new URLSearchParams({ limit: "100" });
  if (state.eventStatus) query.set("status", state.eventStatus);
  if (state.eventType) query.set("event_type", state.eventType);
  state.events = await api(`/api/v1/events?${query.toString()}`);
  renderEvents();
}

async function refreshAll() {
  await refreshCameras();
  await Promise.all([refreshMetrics(), refreshEvents(), refreshJobs(), refreshDemoAssets(), refreshZones()]);
}

function updateSocketStatus(online) {
  const box = $("#socketStatus");
  box.className = `status-pill websocket${online ? " online" : ""}`;
  box.querySelector("span").textContent = online ? "实时通道在线" : "实时通道离线";
  $("#wsLabel").innerHTML = `<i></i> ${online ? "已连接" : "等待连接"}`;
}

function disconnectWebSocket() {
  clearTimeout(state.socketTimer);
  clearInterval(state.socketPing);
  state.socketTimer = null;
  state.socketPing = null;
  if (state.socket) {
    state.socket.onclose = null;
    state.socket.close();
    state.socket = null;
  }
  updateSocketStatus(false);
}

function connectWebSocket() {
  disconnectWebSocket();
  if (!state.token) return;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/events?token=${encodeURIComponent(state.token)}`);
  state.socket = socket;
  socket.addEventListener("open", () => {
    updateSocketStatus(true);
    state.socketPing = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 25000);
  });
  socket.addEventListener("message", (message) => {
    let payload;
    try { payload = JSON.parse(message.data); } catch { return; }
    if (payload.type !== "event" || !payload.event) return;
    const event = payload.event;
    const alreadyLoaded = state.events.some((item) => item.id === event.id);
    if (!alreadyLoaded) {
      state.events.unshift(event);
      renderEvents();
      refreshMetrics().catch(() => {});
      const label = EVENT_TYPES[event.event_type]?.label || event.event_type;
      showToast("收到实时安全告警", `${label} · ${cameraName(event.camera_id)}`, "warning", 6500);
    }
  });
  socket.addEventListener("close", () => {
    clearInterval(state.socketPing);
    updateSocketStatus(false);
    if (state.token) state.socketTimer = setTimeout(connectWebSocket, 3500);
  });
  socket.addEventListener("error", () => updateSocketStatus(false));
}

async function handleLogin(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "正在验证身份...";
  $("#loginStatus").textContent = "正在连接监测服务";
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
    });
    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem("safety_token", state.token);
    localStorage.setItem("safety_user", JSON.stringify(state.user));
    setAuthenticatedUser(state.user);
    await refreshAll();
    $("#loginOverlay").classList.add("hidden");
    connectWebSocket();
    showToast("登录成功", `欢迎进入安全监测平台，${data.user.username}。`, "success");
  } catch (error) {
    $("#loginStatus").textContent = error.message;
    showToast("登录失败", error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "登录系统 →";
  }
}

function setSelectedImage(file) {
  if (!file) return;
  $("#imageFileName").textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  const url = URL.createObjectURL(file);
  $("#preview").src = url;
  $("#preview").style.display = "block";
  $("#stagePlaceholder").classList.add("hidden");
}

function setSelectedVideo(file) {
  if (!file) return;
  $("#videoFileName").textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
}

async function loadDemoAsset(sourceType) {
  const select = $(sourceType === "image" ? "#imageDemoAsset" : "#videoDemoAsset");
  const asset = state.demoAssets.find((item) => item.asset_id === select?.value && item.source_type === sourceType);
  if (!asset) {
    showToast("请选择演示素材", "下拉框中选择一个已归档的本地样例。", "warning");
    return;
  }
  try {
    const response = await fetch(asset.url);
    if (!response.ok) throw new Error(`素材读取失败（${response.status}）`);
    const blob = await response.blob();
    const file = new File([blob], asset.name, { type: blob.type || (sourceType === "image" ? "image/jpeg" : "video/mp4") });
    const input = $(sourceType === "image" ? "#imageFile" : "#videoFile");
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    if (sourceType === "image") setSelectedImage(file);
    else setSelectedVideo(file);
    showToast("演示素材已载入", `${asset.name} 已放入上传框，可直接提交检测。`, "success");
  } catch (error) {
    showToast("演示素材载入失败", error.message, "error");
  }
}

async function handleImageInference(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const cameraId = $("#imageCamera").value;
  if (cameraId) form.append("camera_id", cameraId);
  $("#imageState").className = "state-chip running";
  $("#imageState").textContent = "AI 推理中";
  $("#scanningLine").classList.add("active");
  $("#imageResult").textContent = "检测中...";
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const data = await api("/api/v1/inference/images", { method: "POST", body: form });
    renderImageResult(data);
    const previewUrl = pathToUrl(data.preview_path || data.result_path || data.events?.[0]?.evidence_path);
    if (previewUrl) {
      $("#preview").src = previewUrl;
      $("#preview").style.display = "block";
      $("#stagePlaceholder").classList.add("hidden");
      updateOverviewSnapshot(previewUrl, data.events?.length ? `发现 ${data.events.length} 条安全事件` : "图片检测完成");
    }
    await Promise.all([refreshMetrics(), refreshEvents(), refreshJobs()]);
    showToast("图片检测完成", `识别 ${data.detections?.length || 0} 个目标，产生 ${data.events?.length || 0} 条事件。`, data.events?.length ? "warning" : "success");
  } catch (error) {
    $("#imageState").className = "state-chip error";
    $("#imageState").textContent = "检测失败";
    $("#imageResult").textContent = error.message;
    showToast("图片检测失败", error.message, "error");
  } finally {
    $("#scanningLine").classList.remove("active");
    button.disabled = false;
  }
}

async function handleVideoInference(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const cameraId = $("#videoCamera").value;
  if (cameraId) form.append("camera_id", cameraId);
  $("#jobStatus").textContent = "正在提交任务";
  $("#jobPercent").textContent = "0%";
  $("#jobProgressBar").style.width = "2%";
  $("#jobResultLink").classList.add("hidden");
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const job = await api("/api/v1/inference/videos", { method: "POST", body: form });
    $("#jobIdLabel").textContent = `任务 ID：${job.job_id}`;
    showToast("视频任务已创建", "系统将在后台逐帧检测并生成结果视频。", "info");
    await pollJob(job.job_id);
  } catch (error) {
    $("#jobStatus").textContent = "任务提交失败";
    $("#jobIdLabel").textContent = error.message;
    showToast("视频任务失败", error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function pollJob(jobId) {
  try {
    const job = await api(`/api/v1/jobs/${jobId}`);
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    const labels = { queued: "任务排队中", running: "正在分析视频", completed: "视频分析完成", failed: "视频分析失败" };
    $("#jobStatus").textContent = labels[job.status] || job.status;
    $("#jobPercent").textContent = `${progress.toFixed(1)}%`;
    $("#jobProgressBar").style.width = `${Math.max(progress, job.status === "queued" ? 2 : 0)}%`;
    if (job.error_message) $("#jobIdLabel").textContent = job.error_message;
    if (["queued", "running"].includes(job.status)) {
      setTimeout(() => pollJob(jobId), 1200);
      return;
    }
    if (job.status === "completed") {
      $("#jobResultLink").dataset.jobResult = job.job_id;
      $("#jobResultLink").classList.remove("hidden");
      showToast("视频分析完成", "结果文件和安全事件已经生成。", "success");
    } else {
      showToast("视频分析失败", job.error_message || "请检查视频格式和模型状态。", "error");
    }
    await Promise.all([refreshMetrics(), refreshEvents(), refreshJobs()]);
  } catch (error) {
    $("#jobStatus").textContent = "任务状态获取失败";
    $("#jobIdLabel").textContent = error.message;
    showToast("任务轮询中断", error.message, "error");
  }
}

async function handleCameraCreate(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await api("/api/v1/cameras", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: form.get("name"), source: form.get("source") || "local", location: form.get("location") || null, enabled: true }),
    });
    event.currentTarget.reset();
    event.currentTarget.elements.source.value = "local";
    await Promise.all([refreshCameras(), refreshMetrics()]);
    showToast("监控点已创建", "新设备可用于绑定推理任务和危险区域。", "success");
  } catch (error) {
    showToast("新增监控点失败", error.message, "error");
  }
}

function zoneContext() {
  return $("#zoneCanvas").getContext("2d");
}

function drawZoneCanvas() {
  const canvas = $("#zoneCanvas");
  const ctx = zoneContext();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, "#0b1c2c");
  gradient.addColorStop(1, "#07131f");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "rgba(76, 137, 186, .12)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
  for (let y = 0; y <= canvas.height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
  ctx.fillStyle = "rgba(152, 180, 202, .5)";
  ctx.font = "11px Microsoft YaHei";
  ctx.fillText("危险区域坐标画布  720 × 405", 18, 25);
  if (!state.zonePoints.length) return;
  ctx.beginPath();
  ctx.moveTo(state.zonePoints[0].x, state.zonePoints[0].y);
  state.zonePoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  if (state.zonePoints.length >= 3) ctx.closePath();
  ctx.fillStyle = "rgba(239, 71, 111, .18)";
  ctx.strokeStyle = "#ff587d";
  ctx.lineWidth = 2;
  if (state.zonePoints.length >= 3) ctx.fill();
  ctx.stroke();
  state.zonePoints.forEach((point, index) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = "#ff587d";
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = "#ffb5c6";
    ctx.font = "10px Consolas";
    ctx.fillText(String(index + 1), point.x + 9, point.y - 8);
  });
}

function syncZoneTextarea() {
  const relative = state.zonePoints.map((point) => ({
    x: Number((point.x / ZONE_CANVAS_W).toFixed(3)),
    y: Number((point.y / ZONE_CANVAS_H).toFixed(3)),
  }));
  $('#zoneForm textarea[name="polygon"]').value = JSON.stringify(relative);
}

function parseZoneTextarea(showError = false) {
  try {
    const points = JSON.parse($('#zoneForm textarea[name="polygon"]').value || "[]");
    if (!Array.isArray(points)) throw new Error("坐标必须是数组");
    const isRelative = points.every((point) => Math.abs(Number(point.x)) <= 1 && Math.abs(Number(point.y)) <= 1);
    state.zonePoints = points
      .map((point) => (isRelative
        ? { x: Math.round(Number(point.x) * ZONE_CANVAS_W), y: Math.round(Number(point.y) * ZONE_CANVAS_H) }
        : { x: Number(point.x), y: Number(point.y) }))
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
    syncZoneTextarea();
    drawZoneCanvas();
  } catch (error) {
    if (showError) showToast("坐标格式错误", error.message, "error");
  }
}

async function handleZoneCreate(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const cameraId = form.get("camera_id");
  if (!cameraId) {
    showToast("请选择监控点", "危险区域必须绑定一个监控点。", "warning");
    return;
  }
  parseZoneTextarea(false);
  if (state.zonePoints.length < 3) {
    showToast("危险区域无效", "危险区域至少需要 3 个顶点。", "error");
    return;
  }
  const polygon = state.zonePoints.map((point) => ({
    x: Number((point.x / ZONE_CANVAS_W).toFixed(3)),
    y: Number((point.y / ZONE_CANVAS_H).toFixed(3)),
  }));
  try {
    await api(`/api/v1/cameras/${cameraId}/zones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: form.get("name"), polygon, coordinate_space: "relative", enabled: true }),
    });
    showToast("危险区域已启用", `“${form.get("name")}”已按相对坐标写入规则引擎配置。`, "success");
    await refreshZones();
  } catch (error) {
    showToast("危险区域保存失败", error.message, "error");
  }
}

async function updateEventStatus(eventId, status) {
  try {
    await api(`/api/v1/events/${eventId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    await Promise.all([refreshEvents(), refreshMetrics()]);
    showToast("事件状态已更新", status === "resolved" ? "该事件已完成闭环处理。" : "该事件已由人工确认。", "success");
  } catch (error) {
    showToast("事件处理失败", error.message, "error");
  }
}

function showEvidence(eventId) {
  const event = state.events.find((item) => String(item.id) === String(eventId));
  if (!event?.evidence_path) return;
  $("#evidenceTitle").textContent = EVENT_TYPES[event.event_type]?.label || "告警证据";
  $("#evidenceImage").src = pathToUrl(event.evidence_path);
  $("#evidenceMeta").textContent = `${formatDateTime(event.timestamp).join(" ")} · ${cameraName(event.camera_id)} · Track ID ${event.track_id ?? "--"}`;
  $("#evidenceModal").classList.remove("hidden");
}

function bindInteractions() {
  $$('.nav-item[data-page]').forEach((button) => button.addEventListener("click", () => showPage(button.dataset.page)));
  $$('[data-goto]').forEach((button) => button.addEventListener("click", () => showPage(button.dataset.goto)));
  $("#menuToggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#logoutButton").addEventListener("click", () => logout());
  $("#loginForm").addEventListener("submit", handleLogin);
  $("#imageForm").addEventListener("submit", handleImageInference);
  $("#videoForm").addEventListener("submit", handleVideoInference);
  $("#jobResultLink").addEventListener("click", () => {
    const jobId = $("#jobResultLink").dataset.jobResult;
    if (jobId) showJobResult(jobId).catch((error) => showToast("结果读取失败", error.message, "error"));
  });
  $("#cameraForm").addEventListener("submit", handleCameraCreate);
  $("#zoneForm").addEventListener("submit", handleZoneCreate);
  $("#zoneList").addEventListener("click", async (event) => {
    const load = event.target.closest("[data-zone-load]");
    if (load) {
      const zone = state.zones.find((item) => String(item.id) === load.dataset.zoneLoad);
      if (!zone) return;
      const relative = zone.coordinate_space !== "pixel";
      state.zonePoints = (zone.polygon || []).map((point) => ({
        x: Math.round(relative ? Number(point.x) * ZONE_CANVAS_W : Number(point.x)),
        y: Math.round(relative ? Number(point.y) * ZONE_CANVAS_H : Number(point.y)),
      }));
      syncZoneTextarea();
      drawZoneCanvas();
      showToast("危险区域已载入", `“${zone.name}”的顶点已绘制到画布。`, "info");
      return;
    }
    const remove = event.target.closest("[data-zone-delete]");
    if (remove) {
      try {
        await api(`/api/v1/zones/${remove.dataset.zoneDelete}`, { method: "DELETE" });
        await refreshZones();
        showToast("危险区域已删除", "该区域不再参与越界判断。", "success");
      } catch (error) {
        showToast("删除失败", error.message, "error");
      }
    }
  });
  $("#refreshCameras").addEventListener("click", () => refreshCameras().then(() => showToast("设备列表已刷新", `当前共 ${state.cameras.length} 个监控点。`, "info")).catch((error) => showToast("刷新失败", error.message, "error")));
  $("#refreshEvents").addEventListener("click", () => refreshEvents().then(() => showToast("告警数据已刷新", `已加载 ${state.events.length} 条事件。`, "info")).catch((error) => showToast("刷新失败", error.message, "error")));
  $("#refreshJobs").addEventListener("click", () => refreshJobs().then(() => showToast("任务列表已刷新", `已加载 ${state.jobs.length} 条任务。`, "info")).catch((error) => showToast("刷新失败", error.message, "error")));
  [$("#jobStatusFilter"), $("#jobSourceFilter")].forEach((select) => select.addEventListener("change", () => refreshJobs().catch((error) => showToast("筛选失败", error.message, "error"))));
  $("#refreshExperiments").addEventListener("click", () => refreshExperiments().then(() => showToast("实验数据已刷新", "指标与数据集校验结果已重新读取。", "info")).catch((error) => showToast("刷新失败", error.message, "error")));
  $("#eventTypeFilter").addEventListener("change", (event) => { state.eventType = event.target.value; refreshEvents().catch((error) => showToast("筛选失败", error.message, "error")); });
  $("#eventStatusTabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-status]");
    if (!button) return;
    $$('#eventStatusTabs button').forEach((item) => item.classList.toggle("active", item === button));
    state.eventStatus = button.dataset.status;
    refreshEvents().catch((error) => showToast("筛选失败", error.message, "error"));
  });
  $("#eventsBody").addEventListener("click", (event) => {
    const action = event.target.closest("button[data-event]");
    if (action) updateEventStatus(action.dataset.event, action.dataset.status);
    const evidence = event.target.closest("button[data-evidence]");
    if (evidence) showEvidence(evidence.dataset.evidence);
  });
  $("#jobsBody").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-job-result]");
    if (!button) return;
    showJobResult(button.dataset.jobResult).catch((error) => showToast("结果读取失败", error.message, "error"));
  });
  $("#closeEvidence").addEventListener("click", () => $("#evidenceModal").classList.add("hidden"));
  $("#evidenceModal").addEventListener("click", (event) => { if (event.target.id === "evidenceModal") event.currentTarget.classList.add("hidden"); });
  $("#closeJobResult").addEventListener("click", () => $("#jobResultModal").classList.add("hidden"));
  $("#jobResultModal").addEventListener("click", (event) => { if (event.target.id === "jobResultModal") event.currentTarget.classList.add("hidden"); });

  const imageInput = $("#imageFile");
  imageInput.addEventListener("change", () => setSelectedImage(imageInput.files[0]));
  $("#videoFile").addEventListener("change", (event) => setSelectedVideo(event.currentTarget.files[0]));
  $("#loadImageDemo").addEventListener("click", () => loadDemoAsset("image"));
  $("#loadVideoDemo").addEventListener("click", () => loadDemoAsset("video"));
  ["dragenter", "dragover"].forEach((name) => $("#imageDrop").addEventListener(name, (event) => { event.preventDefault(); $("#imageDrop").classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => $("#imageDrop").addEventListener(name, (event) => { event.preventDefault(); $("#imageDrop").classList.remove("dragging"); }));
  $("#imageDrop").addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    imageInput.files = transfer.files;
    setSelectedImage(file);
  });

  const canvas = $("#zoneCanvas");
  canvas.addEventListener("click", (event) => {
    const rect = canvas.getBoundingClientRect();
    state.zonePoints.push({ x: Math.round((event.clientX - rect.left) * (canvas.width / rect.width)), y: Math.round((event.clientY - rect.top) * (canvas.height / rect.height)) });
    syncZoneTextarea();
    drawZoneCanvas();
  });
  $("#undoZonePoint").addEventListener("click", () => { state.zonePoints.pop(); syncZoneTextarea(); drawZoneCanvas(); });
  $("#clearZonePoints").addEventListener("click", () => { state.zonePoints = []; syncZoneTextarea(); drawZoneCanvas(); });
  $('#zoneForm textarea[name="polygon"]').addEventListener("change", () => parseZoneTextarea(true));
  window.addEventListener("resize", () => { if ($('[data-page-panel="configuration"]').classList.contains("active")) drawZoneCanvas(); });
}

async function initialise() {
  bindInteractions();
  updateClock();
  setInterval(updateClock, 1000);
  parseZoneTextarea();
  await refreshHealth();
  if (!state.token) return;
  setAuthenticatedUser(state.user);
  try {
    await refreshAll();
    $("#loginOverlay").classList.add("hidden");
    connectWebSocket();
  } catch (error) {
    if (error.status === 401) {
      logout(false);
      $("#loginStatus").textContent = "登录已过期，请重新登录";
    } else {
      showToast("工作台数据加载失败", error.message, "error");
    }
  }
}

initialise();
