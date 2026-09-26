<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useAppStore } from '../store'
import { eventIcon, eventLabel, formatDateTime } from '../utils'

const store = useAppStore()

const donutRef = ref(null)
const trendRef = ref(null)
let donutChart = null
let trendChart = null

const TYPE_COLORS = { no_helmet: '#ef476f', no_vest: '#f59e0b', intrusion: '#1477ff' }
const TYPE_NAMES = { no_helmet: '未佩戴安全帽', no_vest: '未穿反光背心', intrusion: '危险区域闯入' }

function renderDonut() {
  if (!donutChart) return
  const types = store.metrics?.events_by_type || {}
  const data = Object.keys(TYPE_NAMES).map((key) => ({
    name: TYPE_NAMES[key],
    value: Number(types[key] || 0),
    itemStyle: { color: TYPE_COLORS[key] }
  }))
  const total = data.reduce((sum, item) => sum + item.value, 0)
  donutChart.setOption({
    tooltip: { trigger: 'item' },
    title: {
      text: String(total),
      subtext: '事件总数',
      left: 'center',
      top: '38%',
      textStyle: { fontSize: 22, fontWeight: 600 },
      subtextStyle: { fontSize: 10, color: '#8997a7' }
    },
    series: [
      {
        type: 'pie',
        radius: ['58%', '80%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
        label: { show: false },
        data
      }
    ]
  })
}

// New analytical chart: event volume per day over the last 7 days, derived
// from the loaded event list (limit 100 per query).
const trendDays = computed(() => {
  const buckets = new Map()
  for (let offset = 6; offset >= 0; offset -= 1) {
    const date = new Date()
    date.setDate(date.getDate() - offset)
    const key = date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
    buckets.set(key, 0)
  }
  for (const event of store.events) {
    const key = new Date(event.timestamp).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
    if (buckets.has(key)) buckets.set(key, buckets.get(key) + 1)
  }
  return { labels: [...buckets.keys()], values: [...buckets.values()] }
})

function renderTrend() {
  if (!trendChart) return
  const { labels, values } = trendDays.value
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 28 },
    xAxis: { type: 'category', data: labels, boundaryGap: false, axisLine: { lineStyle: { color: '#dfe7ee' } }, axisLabel: { color: '#718295', fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#eef2f6' } }, axisLabel: { color: '#718295', fontSize: 10 } },
    series: [
      {
        name: '安全事件',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: values,
        lineStyle: { width: 3, color: '#1477ff' },
        itemStyle: { color: '#1477ff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(20,119,255,.25)' },
            { offset: 1, color: 'rgba(20,119,255,0)' }
          ])
        }
      }
    ]
  })
}

const metricCards = computed(() => {
  const metrics = store.metrics
  return [
    { cls: 'danger', icon: '!', label: '累计安全告警', value: metrics?.total_events ?? 0, note: metrics?.total_events ? `已闭环 ${metrics.resolved_events ?? 0} 条事件` : '等待监测数据' },
    { cls: 'warning', icon: '⌛', label: '当前待处理', value: metrics?.open_events ?? 0, note: '需要人工确认' },
    { cls: 'success', icon: '●', label: '在线监控点', value: metrics?.active_cameras ?? 0, note: '配置已生效' },
    { cls: 'info', icon: '▶', label: '今日推理任务', value: metrics?.jobs_today ?? 0, note: '图片与视频任务' }
  ]
})

const severityRows = computed(() => {
  const severity = store.metrics?.events_by_severity || {}
  const total = store.metrics?.total_events || 0
  return [
    { key: 'critical', label: '严重', color: '#b82e4e', count: severity.critical || 0 },
    { key: 'high', label: '高危', color: '#ef476f', count: severity.high || 0 },
    { key: 'medium', label: '中危', color: '#f59e0b', count: severity.medium || 0 },
    { key: 'low', label: '低危', color: '#0abf87', count: severity.low || 0 }
  ].map((row) => ({ ...row, width: total ? `${Math.max((row.count / total) * 100, row.count ? 4 : 0)}%` : '0%' }))
})

const legendRows = computed(() => {
  const types = store.metrics?.events_by_type || {}
  return Object.keys(TYPE_NAMES).map((key) => ({ key, label: TYPE_NAMES[key], color: TYPE_COLORS[key], count: Number(types[key] || 0) }))
})

function handleResize() {
  donutChart?.resize()
  trendChart?.resize()
}

onMounted(async () => {
  donutChart = echarts.init(donutRef.value)
  trendChart = echarts.init(trendRef.value)
  renderDonut()
  renderTrend()
  window.addEventListener('resize', handleResize)
  if (store.token) {
    await Promise.all([store.refreshMetrics(), store.refreshEvents(), store.refreshCameras(), store.refreshHealth()])
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  donutChart?.dispose()
  trendChart?.dispose()
})

watch(() => store.metrics, renderDonut, { deep: true })
watch(trendDays, renderTrend, { deep: true })
</script>

<template>
  <section>
    <div class="hero-banner">
      <div>
        <span class="hero-tag"><i></i> AI SAFETY ONLINE</span>
        <h2>工业作业现场安全态势</h2>
        <p>YOLOv8 PPE 检测 · ByteTrack 人员跟踪 · 危险区域越界监测</p>
      </div>
      <div class="hero-stats">
        <div><span>连续帧确认</span><strong>3 帧</strong></div>
        <div><span>告警冷却</span><strong>10 秒</strong></div>
        <div><span>规则引擎</span><strong>已启用</strong></div>
      </div>
      <svg class="hero-grid" viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden="true"><path d="M0 120 95 75l72 17 92-62 141 38M0 93l110-31 86 13 67-45 137 20"/><circle cx="259" cy="30" r="5"/><circle cx="167" cy="92" r="4"/></svg>
    </div>

    <section class="metric-grid">
      <article v-for="card in metricCards" :key="card.label" class="metric-card" :class="card.cls">
        <div class="metric-icon">{{ card.icon }}</div>
        <div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div>
      </article>
    </section>

    <div class="overview-grid">
      <article class="panel trend-panel">
        <div class="panel-heading"><div><span class="section-label">ALERT ANALYTICS</span><h3>告警类型分布</h3></div><span class="period-tag">当前全部数据</span></div>
        <div class="analytics-body">
          <div ref="donutRef" style="width:190px;height:190px"></div>
          <div style="display:grid;align-content:center;gap:18px">
            <div class="donut-legend">
              <div v-for="row in legendRows" :key="row.key">
                <i class="legend-dot" :style="{ background: row.color }"></i>
                <span>{{ row.label }}</span>
                <strong>{{ row.count }}</strong>
              </div>
            </div>
            <div class="severity-bars">
              <div class="bar-title"><span>告警等级构成</span><small>事件数 / 占比</small></div>
              <div v-for="row in severityRows" :key="row.key" class="bar-row">
                <label>{{ row.label }}</label>
                <div><i :style="{ width: row.width, background: row.color }"></i></div>
                <strong>{{ row.count }}</strong>
              </div>
            </div>
          </div>
        </div>
      </article>

      <article class="panel system-panel">
        <div class="panel-heading"><div><span class="section-label">SYSTEM STATUS</span><h3>推理服务状态</h3></div><span class="online-badge"><i></i> ONLINE</span></div>
        <div class="system-core">
          <div class="radar"><i></i><i></i><i></i><span>AI</span></div>
          <div>
            <strong>{{ store.health?.detector_backend || '--' }}</strong>
            <span>当前检测后端</span>
            <small>{{ store.health?.model_available ? '模型已加载' : '模型不可用' }}</small>
          </div>
        </div>
        <div class="status-list">
          <div><span>目标检测</span><strong><i></i> YOLOv8</strong></div>
          <div><span>多目标跟踪</span><strong><i></i> ByteTrack</strong></div>
          <div><span>规则判断</span><strong><i></i> PPE / 越界</strong></div>
          <div><span>实时消息</span><strong><i></i> {{ store.socketOnline ? '已连接' : '等待连接' }}</strong></div>
        </div>
      </article>

      <article class="panel recent-panel">
        <div class="panel-heading"><div><span class="section-label">LIVE EVENTS</span><h3>最新安全事件</h3></div><router-link to="/alerts" class="text-button" style="text-decoration:none">查看全部 →</router-link></div>
        <div class="event-feed">
          <div v-if="!store.events.length" class="empty-state compact"><span>◎</span><p>暂无安全事件</p></div>
          <div v-for="event in store.events.slice(0, 4)" :key="event.id" class="event-feed-item">
            <div class="event-symbol">{{ eventIcon(event.event_type) }}</div>
            <div>
              <strong>{{ eventLabel(event.event_type) }}</strong>
              <span>{{ event.message || `监控点 ${store.cameraName(event.camera_id)} · Track ${event.track_id ?? '--'}` }}</span>
            </div>
            <time>{{ formatDateTime(event.timestamp).date }}<br />{{ formatDateTime(event.timestamp).time }}</time>
          </div>
        </div>
      </article>

      <article class="panel camera-panel">
        <div class="panel-heading"><div><span class="section-label">MONITOR POINTS</span><h3>监控点运行状态</h3></div><button class="icon-text-button" type="button" @click="store.refreshCameras()">↻ 刷新</button></div>
        <div class="camera-overview">
          <div v-if="!store.cameras.length" class="empty-state compact"><span>⌁</span><p>暂无摄像头</p></div>
          <div v-for="camera in store.cameras.slice(0, 4)" :key="camera.id" class="camera-preview-card">
            <strong>{{ camera.name }}</strong>
            <span>{{ camera.location || camera.source || '本地视频源' }}</span>
          </div>
        </div>
      </article>
    </div>

    <article class="panel" style="margin-top:14px">
      <div class="panel-heading"><div><span class="section-label">EVENT TREND</span><h3>近 7 天告警趋势</h3></div><span class="period-tag">基于最近加载的事件记录</span></div>
      <div ref="trendRef" style="width:100%;height:240px;padding:10px 12px;box-sizing:border-box"></div>
    </article>
  </section>
</template>
