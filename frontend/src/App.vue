<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from './store'
import { eventIcon, eventLabel, formatDateTime, isVideoPreview, pathToUrl } from './utils'

const store = useAppStore()
const route = useRoute()

const NAV_ITEMS = [
  { name: 'overview', label: '监控总览', icon: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z', live: true },
  { name: 'detection', label: '智能检测', icon: 'M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3' },
  { name: 'jobs', label: '任务中心', icon: 'M4 6h16M4 12h16M4 18h10' },
  { name: 'experiments', label: '模型实验', icon: 'M9 3h6M10 3v6l-5.5 8.5A2.2 2.2 0 0 0 6.3 21h11.4a2.2 2.2 0 0 0 1.8-3.5L14 9V3M8 15h8' },
  { name: 'alerts', label: '告警中心', icon: 'M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4', badge: true },
  { name: 'configuration', label: '设备与区域', icon: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm8.4 6a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.1a1.7 1.7 0 0 0-1.4-1.5 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.6-1H3v-4h.1a1.7 1.7 0 0 0 1.5-1.4 1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6V3h4v.1a1.7 1.7 0 0 0 1.4 1.5 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.2.38.4.72.6 1 .28.4.66.4 1.1.4h.1v4h-.1a1.7 1.7 0 0 0-1.6 1Z' }
]

const now = ref(new Date())
let clockTimer = null
onMounted(() => {
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
  store.boot()
})
onBeforeUnmount(() => clearInterval(clockTimer))

const clockTime = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const clockDate = computed(() => now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }))

const healthPill = computed(() => {
  if (store.healthError) return { cls: 'error', text: '推理服务异常' }
  if (store.health) return { cls: 'online', text: `${store.health.status === 'ok' ? '服务正常' : store.health.status} · ${store.health.detector_backend}` }
  return { cls: '', text: '服务连接中' }
})

const modelStatus = computed(() => {
  if (store.healthError) return store.healthError
  if (!store.health) return '读取模型状态中'
  if (store.health.model_available) {
    const modelPath = String(store.health.model_path || '').split(/[\\/]/).pop() || '已加载权重'
    return `${modelPath}${store.health.image_size ? ` · ${store.health.image_size}px` : ''}`
  }
  return `模型不可用${store.health.model_error ? `：${store.health.model_error}` : ''}`
})

const loginForm = ref({ username: 'admin', password: 'admin123' })
const loginBusy = ref(false)
const loginStatus = ref('演示账号：admin / admin123')

async function handleLogin() {
  loginBusy.value = true
  loginStatus.value = '正在连接监测服务'
  try {
    await store.login(loginForm.value.username, loginForm.value.password)
    loginStatus.value = '演示账号：admin / admin123'
  } catch (error) {
    loginStatus.value = error.message
  } finally {
    loginBusy.value = false
  }
}

const evidence = computed(() => store.evidenceEvent)
const evidenceVisible = computed({
  get: () => Boolean(store.evidenceEvent),
  set: (value) => {
    if (!value) store.evidenceEvent = null
  }
})

const jobResultVisible = computed({
  get: () => Boolean(store.jobResult),
  set: (value) => {
    if (!value) store.jobResult = null
  }
})
const jobPreviewUrl = computed(() => pathToUrl(store.jobResult?.preview_path))
const jobIsVideo = computed(() => isVideoPreview(store.jobResult?.preview_path))

const jobStats = computed(() => {
  const result = store.jobResult
  if (!result) return []
  const detections = result.detections_by_class || {}
  return [
    ['检测目标', result.detection_count ?? 0],
    ['人员', detections.person || 0],
    ['安全帽', detections.helmet || 0],
    ['反光背心', detections.vest || 0]
  ]
})

const EVENT_LABELS = { no_helmet: '未佩戴安全帽', no_vest: '未穿反光背心', intrusion: '危险区域闯入' }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" id="sidebar">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 48 48"><path d="M24 4 42 11v12c0 11.2-7.6 18.1-18 21C13.6 41.1 6 34.2 6 23V11l18-7Z"/><path d="m15 24 6 6 12-13"/></svg>
        </div>
        <div><strong>SAFEVISION</strong><span>工业安全智能监测</span></div>
      </div>

      <nav class="side-nav" aria-label="主导航">
        <p class="nav-caption">控制台</p>
        <router-link
          v-for="item in NAV_ITEMS"
          :key="item.name"
          :to="`/${item.name}`"
          class="nav-item"
          :class="{ active: route.name === item.name }"
        >
          <svg viewBox="0 0 24 24"><path :d="item.icon"/></svg>
          <span>{{ item.label }}</span>
          <i v-if="item.live" class="nav-live"></i>
          <b v-if="item.badge && store.openEventCount">{{ store.openEventCount }}</b>
        </router-link>
      </nav>

      <div class="sidebar-summary">
        <div class="summary-head"><span>系统负载</span><strong>正常</strong></div>
        <div class="load-track"><i></i></div>
        <p><span class="pulse-dot"></span> 推理服务运行中</p>
      </div>

      <div class="sidebar-user" v-if="store.isLoggedIn">
        <div class="avatar">管</div>
        <div><strong>{{ store.user?.username || '用户' }}</strong><span>{{ store.user?.role === 'admin' ? '系统管理员' : store.user?.role || '普通用户' }}</span></div>
        <button class="icon-button" type="button" title="退出登录" @click="store.logout()">↪</button>
      </div>
    </aside>

    <main class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <div><p>{{ route.meta.eyebrow }}</p><h1>{{ route.meta.title }}</h1></div>
        </div>
        <div class="topbar-actions">
          <div class="status-pill" :class="healthPill.cls"><i></i><span>{{ healthPill.text }}</span></div>
          <div class="status-pill websocket" :class="{ online: store.socketOnline }"><i></i><span>{{ store.socketOnline ? '实时通道在线' : '实时通道离线' }}</span></div>
          <div class="clock"><strong>{{ clockTime }}</strong><span>{{ clockDate }}</span></div>
          <router-link to="/detection" class="primary compact-button" style="text-decoration: none">＋ 发起检测</router-link>
        </div>
      </header>

      <div class="content">
        <router-view />
      </div>
    </main>

    <div class="auth-overlay" v-if="!store.isLoggedIn">
      <section class="login-card">
        <div class="login-visual">
          <div class="brand-mark large"><svg viewBox="0 0 48 48"><path d="M24 4 42 11v12c0 11.2-7.6 18.1-18 21C13.6 41.1 6 34.2 6 23V11l18-7Z"/><path d="m15 24 6 6 12-13"/></svg></div>
          <span>INDUSTRIAL AI SAFETY</span>
          <h2>让每一次作业<br />都处于安全视野之内</h2>
          <p>YOLOv8 + ByteTrack 工业人员安全防护与危险区域智能监测</p>
          <div class="login-features"><span>人员检测</span><span>PPE 识别</span><span>越界告警</span></div>
        </div>
        <div class="login-form-wrap">
          <div class="mobile-brand">SAFEVISION</div>
          <span class="section-label">WELCOME BACK</span>
          <h2>登录监测平台</h2>
          <p>使用系统账户进入安全监控工作台</p>
          <form @submit.prevent="handleLogin">
            <label><span>用户名</span><input v-model="loginForm.username" autocomplete="username" /></label>
            <label><span>密码</span><input v-model="loginForm.password" type="password" autocomplete="current-password" /></label>
            <button class="primary full-button" type="submit" :disabled="loginBusy">{{ loginBusy ? '正在验证身份...' : '登录系统 →' }}</button>
          </form>
          <div class="login-status"><span>{{ loginStatus }}</span></div>
        </div>
      </section>
    </div>

    <el-dialog v-model="evidenceVisible" :title="evidence ? eventLabel(evidence.event_type) : '告警证据'" width="720px">
      <img v-if="evidence?.evidence_path" :src="pathToUrl(evidence.evidence_path)" alt="告警证据截图" style="display:block;width:100%;max-height:60vh;object-fit:contain;background:#07131f" />
      <p v-if="evidence" style="margin:12px 0 0;color:#77889a;font-size:12px">
        {{ formatDateTime(evidence.timestamp).time }} {{ formatDateTime(evidence.timestamp).date }} · {{ store.cameraName(evidence.camera_id) }} · Track ID {{ evidence.track_id ?? '--' }}
      </p>
    </el-dialog>

    <el-dialog v-model="jobResultVisible" title="推理任务结果详情" width="920px" top="6vh">
      <template v-if="store.jobResult">
        <div class="job-result-body">
          <div class="job-result-preview">
            <video v-if="jobIsVideo" controls preload="metadata" :src="jobPreviewUrl"></video>
            <img v-else-if="jobPreviewUrl" :src="jobPreviewUrl" alt="推理标注结果" />
            <div v-else class="empty-state compact"><span>◌</span><p>暂无可视化预览</p></div>
          </div>
          <div class="job-result-side">
            <div class="job-result-summary">
              <div v-for="[label, value] in jobStats" :key="label" class="job-result-stat"><span>{{ label }}</span><strong>{{ value }}</strong></div>
            </div>
            <p class="job-result-note">
              {{ store.jobResult.frames ? `${store.jobResult.frames} 帧` : '单帧图片' }} ·
              {{ store.jobResult.event_count ? `发现 ${store.jobResult.event_count} 条安全事件` : '未发现安全事件' }}
            </p>
            <div class="job-result-events">
              <div v-for="(count, type) in store.jobResult.events_by_type" :key="type" class="job-result-event">
                <strong>{{ EVENT_LABELS[type] || type }} · {{ count }} 条</strong>
                <span>已记录证据，可在告警中心继续确认或关闭。</span>
              </div>
              <div v-if="!store.jobResult.event_count" class="job-result-event" style="border-color:#dcece7;background:#f4fbf8">
                <strong style="color:#168265">✓ 本次未发现安全事件</strong>
                <span>检测结果已生成，可继续查看标注媒体。</span>
              </div>
            </div>
            <div class="job-result-actions">
              <a v-if="jobPreviewUrl" class="primary" :href="jobPreviewUrl" target="_blank" rel="noopener">{{ jobIsVideo ? '打开结果视频' : '打开标注图片' }}</a>
              <a class="outline-button" :href="pathToUrl(store.jobResult.result_path)" target="_blank" rel="noopener">查看原始 JSON</a>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
