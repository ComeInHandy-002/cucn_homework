<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useAppStore } from '../store'
import * as api from '../api'

const store = useAppStore()

// ---- 摄像头管理 ----
const cameraForm = reactive({ name: '', source: 'local', location: '' })
const cameraBusy = ref(false)

async function createCamera() {
  if (!cameraForm.name) return
  cameraBusy.value = true
  try {
    await api.createCamera({ name: cameraForm.name, source: cameraForm.source || 'local', location: cameraForm.location || null, enabled: true })
    cameraForm.name = ''
    cameraForm.location = ''
    await Promise.all([store.refreshCameras(), store.refreshMetrics()])
    store.notify('监控点已创建', '新设备可用于绑定推理任务和危险区域', 'success')
  } catch (error) {
    store.notify('新增监控点失败', error.message, 'error')
  } finally {
    cameraBusy.value = false
  }
}

// ---- 危险区域画布 ----
const ZONE_CANVAS_W = 720
const ZONE_CANVAS_H = 405
const canvasRef = ref(null)
const zonePoints = ref([])
const zoneForm = reactive({ cameraId: '', name: '主危险区', polygon: '' })
const zoneBusy = ref(false)
const selectedZoneId = ref(null)

function drawZoneCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
  gradient.addColorStop(0, '#0b1c2c')
  gradient.addColorStop(1, '#07131f')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.strokeStyle = 'rgba(76, 137, 186, .12)'
  ctx.lineWidth = 1
  for (let x = 0; x <= canvas.width; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke() }
  for (let y = 0; y <= canvas.height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke() }
  ctx.fillStyle = 'rgba(152, 180, 202, .5)'
  ctx.font = '11px Microsoft YaHei'
  ctx.fillText('危险区域坐标画布  720 × 405', 18, 25)
  if (!zonePoints.value.length) return
  ctx.beginPath()
  ctx.moveTo(zonePoints.value[0].x, zonePoints.value[0].y)
  zonePoints.value.slice(1).forEach((point) => ctx.lineTo(point.x, point.y))
  if (zonePoints.value.length >= 3) ctx.closePath()
  ctx.fillStyle = 'rgba(239, 71, 111, .18)'
  ctx.strokeStyle = '#ff587d'
  ctx.lineWidth = 2
  if (zonePoints.value.length >= 3) ctx.fill()
  ctx.stroke()
  zonePoints.value.forEach((point, index) => {
    ctx.beginPath()
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.strokeStyle = '#ff587d'
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.fillStyle = '#ffb5c6'
    ctx.font = '10px Consolas'
    ctx.fillText(String(index + 1), point.x + 9, point.y - 8)
  })
}

function syncZoneTextarea() {
  zoneForm.polygon = JSON.stringify(
    zonePoints.value.map((point) => ({
      x: Number((point.x / ZONE_CANVAS_W).toFixed(3)),
      y: Number((point.y / ZONE_CANVAS_H).toFixed(3))
    }))
  )
}

// Textarea accepts both relative 0-1 values (canonical) and legacy canvas
// pixels; everything is normalised back to canvas space for drawing.
function parseZoneTextarea(showError = false) {
  try {
    const points = JSON.parse(zoneForm.polygon || '[]')
    if (!Array.isArray(points)) throw new Error('坐标必须是数组')
    const isRelative = points.every((point) => Math.abs(Number(point.x)) <= 1 && Math.abs(Number(point.y)) <= 1)
    zonePoints.value = points
      .map((point) => (isRelative
        ? { x: Math.round(Number(point.x) * ZONE_CANVAS_W), y: Math.round(Number(point.y) * ZONE_CANVAS_H) }
        : { x: Number(point.x), y: Number(point.y) }))
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    syncZoneTextarea()
    drawZoneCanvas()
  } catch (error) {
    if (showError) store.notify('坐标格式错误', error.message, 'error')
  }
}

function onCanvasClick(event) {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  zonePoints.value.push({
    x: Math.round((event.clientX - rect.left) * (canvas.width / rect.width)),
    y: Math.round((event.clientY - rect.top) * (canvas.height / rect.height))
  })
  syncZoneTextarea()
  drawZoneCanvas()
}

function undoZonePoint() {
  zonePoints.value.pop()
  syncZoneTextarea()
  drawZoneCanvas()
}

function clearZonePoints() {
  zonePoints.value = []
  syncZoneTextarea()
  drawZoneCanvas()
}

async function createZone() {
  if (!zoneForm.cameraId) {
    store.notify('请选择监控点', '危险区域必须绑定一个监控点', 'warning')
    return
  }
  parseZoneTextarea(false)
  if (zonePoints.value.length < 3) {
    store.notify('危险区域无效', '危险区域至少需要 3 个顶点', 'error')
    return
  }
  const polygon = zonePoints.value.map((point) => ({
    x: Number((point.x / ZONE_CANVAS_W).toFixed(3)),
    y: Number((point.y / ZONE_CANVAS_H).toFixed(3))
  }))
  zoneBusy.value = true
  try {
    await api.createZone(zoneForm.cameraId, { name: zoneForm.name, polygon, coordinate_space: 'relative', enabled: true })
    store.notify('危险区域已启用', `“${zoneForm.name}”已按相对坐标写入规则引擎配置`, 'success')
    await store.refreshZones()
  } catch (error) {
    store.notify('危险区域保存失败', error.message, 'error')
  } finally {
    zoneBusy.value = false
  }
}

function loadZone(zone) {
  const relative = zone.coordinate_space !== 'pixel'
  zonePoints.value = (zone.polygon || []).map((point) => ({
    x: Math.round(relative ? Number(point.x) * ZONE_CANVAS_W : Number(point.x)),
    y: Math.round(relative ? Number(point.y) * ZONE_CANVAS_H : Number(point.y))
  }))
  selectedZoneId.value = zone.id
  zoneForm.name = zone.name
  if (zone.camera_id !== null && zone.camera_id !== undefined) zoneForm.cameraId = String(zone.camera_id)
  syncZoneTextarea()
  drawZoneCanvas()
  store.notify('危险区域已载入', `“${zone.name}”的顶点已绘制到画布`, 'info')
}

async function removeZone(zone) {
  try {
    await store.removeZone(zone.id)
    if (selectedZoneId.value === zone.id) {
      selectedZoneId.value = null
      clearZonePoints()
    }
  } catch (error) {
    store.notify('删除失败', error.message, 'error')
  }
}

onMounted(async () => {
  await nextTick()
  parseZoneTextarea(false)
  drawZoneCanvas()
})

watch(() => store.zones.length, () => drawZoneCanvas())
</script>

<template>
  <section>
    <div class="page-intro">
      <div><span class="section-label">MONITOR CONFIGURATION</span><h2>设备与危险区域</h2><p>维护监控点，并在画面坐标系中绘制作业危险区域。</p></div>
      <span class="permission-tag">管理员配置</span>
    </div>

    <div class="config-grid">
      <article class="panel camera-config">
        <div class="panel-heading"><div><span class="section-label">CAMERAS</span><h3>监控点管理</h3></div><span class="count-tag">{{ store.cameras.length }} 个设备</span></div>
        <form class="form-grid" @submit.prevent="createCamera">
          <label><span>监控点名称</span><input v-model="cameraForm.name" placeholder="例如：一号车间入口" required /></label>
          <label><span>视频源</span><input v-model="cameraForm.source" placeholder="local 或文件路径" /></label>
          <label><span>安装位置</span><input v-model="cameraForm.location" placeholder="例如：A 区北侧" /></label>
          <button class="primary" type="submit" :disabled="cameraBusy">＋ 新增监控点</button>
        </form>
        <div class="camera-list">
          <div v-if="!store.cameras.length" class="empty-state compact"><span>⌁</span><p>暂无监控点配置</p></div>
          <div v-for="camera in store.cameras" :key="camera.id" class="camera-item">
            <div class="camera-item-icon">◉</div>
            <div><strong>{{ camera.name }}</strong><span>{{ camera.location || camera.source || 'local' }}</span></div>
            <div class="camera-state">● {{ camera.enabled ? '运行中' : '已停用' }}</div>
          </div>
        </div>
      </article>

      <article class="panel zone-config">
        <div class="panel-heading">
          <div><span class="section-label">DANGER ZONE</span><h3>危险区域绘制</h3></div>
          <div class="canvas-actions">
            <span class="count-tag">{{ store.zones.length }} 个区域</span>
            <button class="icon-text-button" type="button" @click="undoZonePoint">↶ 撤销</button>
            <button class="icon-text-button danger-text" type="button" @click="clearZonePoints">× 清空</button>
          </div>
        </div>
        <div class="zone-canvas-wrap">
          <canvas ref="canvasRef" width="720" height="405" @click="onCanvasClick"></canvas>
          <div class="canvas-tip"><span>＋</span> 点击画面依次添加多边形顶点（至少 3 个）；坐标按 0–1 相对值保存，适配任意分辨率视频</div>
        </div>
        <form class="zone-form" @submit.prevent="createZone">
          <label><span>绑定监控点</span>
            <el-select v-model="zoneForm.cameraId" placeholder="选择监控点" size="default" style="width:100%">
              <el-option label="未绑定监控点" value="" />
              <el-option v-for="camera in store.cameras" :key="camera.id" :label="camera.name" :value="String(camera.id)" />
            </el-select>
          </label>
          <label><span>区域名称</span><input v-model="zoneForm.name" required /></label>
          <label class="advanced-json"><span>坐标数据（0–1 相对值）</span><textarea v-model="zoneForm.polygon" rows="3" @change="parseZoneTextarea(true)"></textarea></label>
          <button class="primary" type="submit" :disabled="zoneBusy">保存并启用危险区域</button>
        </form>
        <div class="camera-list">
          <div v-if="!store.zones.length" class="empty-state compact"><span>◌</span><p>暂无危险区域</p></div>
          <div v-for="zone in store.zones" :key="zone.id" class="camera-item">
            <div class="camera-item-icon">⬠</div>
            <div>
              <strong>{{ zone.name }}</strong>
              <span>{{ store.cameraName(zone.camera_id) }} · {{ zone.polygon?.length ?? 0 }} 个顶点 · {{ zone.coordinate_space === 'relative' ? '相对坐标' : '像素坐标' }}</span>
            </div>
            <div class="zone-item-actions" style="display:flex;gap:4px">
              <button class="text-button" type="button" @click="loadZone(zone)">载入画布</button>
              <button class="icon-text-button danger-text" type="button" @click="removeZone(zone)">删除</button>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
