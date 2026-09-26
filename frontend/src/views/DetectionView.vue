<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useAppStore } from '../store'
import * as api from '../api'
import { classLabel, isVideoPreview, pathToUrl } from '../utils'

const store = useAppStore()

// ---- 图片检测 ----
const imageFileInput = ref(null)
const imageFileName = ref('')
const imageFile = ref(null)
const previewUrl = ref('')
const imageCameraId = ref('')
const imageState = ref('idle')
const imageBusy = ref(false)
const imageResult = ref(null)
const dragging = ref(false)
const imageDemoAsset = ref('')

const imageDemoOptions = computed(() => store.demoAssets.filter((asset) => asset.source_type === 'image'))

function setImageFile(file) {
  if (!file) return
  imageFile.value = file
  imageFileName.value = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
  previewUrl.value = URL.createObjectURL(file)
}

function onImagePick(event) {
  setImageFile(event.target.files[0])
}

function onImageDrop(event) {
  dragging.value = false
  const file = event.dataTransfer.files[0]
  if (!file) return
  const transfer = new DataTransfer()
  transfer.items.add(file)
  imageFileInput.value.files = transfer.files
  setImageFile(file)
}

async function loadImageDemo() {
  const asset = store.demoAssets.find((item) => item.asset_id === imageDemoAsset.value && item.source_type === 'image')
  if (!asset) {
    store.notify('请选择演示素材', '下拉框中选择一个已归档的本地样例', 'warning')
    return
  }
  try {
    const response = await fetch(asset.url)
    if (!response.ok) throw new Error(`素材读取失败（${response.status}）`)
    const blob = await response.blob()
    const file = new File([blob], asset.name, { type: blob.type || 'image/jpeg' })
    const transfer = new DataTransfer()
    transfer.items.add(file)
    imageFileInput.value.files = transfer.files
    setImageFile(file)
    store.notify('演示素材已载入', `${asset.name} 已放入上传框，可直接提交检测`, 'success')
  } catch (error) {
    store.notify('演示素材载入失败', error.message, 'error')
  }
}

const detectionCounts = computed(() => {
  const counts = { person: 0, helmet: 0, vest: 0, total: 0 }
  for (const detection of imageResult.value?.detections || []) {
    const key = String(detection.class_name || '').trim().toLowerCase()
    if (key in counts && key !== 'total') counts[key] += 1
    counts.total += 1
  }
  return counts
})

const imageAlert = computed(() => {
  const events = imageResult.value?.events || []
  if (events.length) {
    return {
      cls: 'has-alerts',
      icon: '!',
      title: `发现 ${events.length} 条安全事件`,
      text: events.map((event) => `${event.event_type === 'no_helmet' ? '未佩戴安全帽' : event.event_type === 'no_vest' ? '未穿反光背心' : '危险区域闯入'}`).join('、')
    }
  }
  return { cls: '', icon: '✓', title: '未发现已确认安全事件', text: '检测结果已完成结构化分析' }
})

async function submitImage() {
  if (!imageFile.value) return
  const form = new FormData()
  form.append('file', imageFile.value)
  if (imageCameraId.value) form.append('camera_id', imageCameraId.value)
  imageBusy.value = true
  imageState.value = 'running'
  try {
    imageResult.value = await api.inferImage(form)
    imageState.value = 'success'
    previewUrl.value = pathToUrl(imageResult.value.preview_path || imageResult.value.events?.[0]?.evidence_path || '')
    await Promise.all([store.refreshMetrics(), store.refreshEvents(), store.refreshJobs()])
    store.notify('图片检测完成', `识别 ${imageResult.value.detections?.length || 0} 个目标，产生 ${imageResult.value.events?.length || 0} 条事件`, imageResult.value.events?.length ? 'warning' : 'success')
  } catch (error) {
    imageState.value = 'error'
    store.notify('图片检测失败', error.message, 'error')
  } finally {
    imageBusy.value = false
  }
}

// ---- 视频任务 ----
const videoFileInput = ref(null)
const videoFileName = ref('')
const videoCameraId = ref('')
const videoBusy = ref(false)
const videoDemoAsset = ref('')
const job = ref({ id: '', status: '', progress: 0, error: '' })
let pollTimer = null

const videoDemoOptions = computed(() => store.demoAssets.filter((asset) => asset.source_type === 'video'))
const JOB_STATUS_TEXT = { queued: '任务排队中', running: '正在分析视频', completed: '视频分析完成', failed: '视频分析失败' }

function onVideoPick(event) {
  const file = event.target.files[0]
  if (!file) return
  videoFileName.value = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
}

async function loadVideoDemo() {
  const asset = store.demoAssets.find((item) => item.asset_id === videoDemoAsset.value && item.source_type === 'video')
  if (!asset) {
    store.notify('请选择演示素材', '下拉框中选择一个已归档的本地样例', 'warning')
    return
  }
  try {
    const response = await fetch(asset.url)
    if (!response.ok) throw new Error(`素材读取失败（${response.status}）`)
    const blob = await response.blob()
    const file = new File([blob], asset.name, { type: blob.type || 'video/mp4' })
    const transfer = new DataTransfer()
    transfer.items.add(file)
    videoFileInput.value.files = transfer.files
    videoFileName.value = `${asset.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
    store.notify('演示素材已载入', `${asset.name} 已放入上传框，可直接提交检测`, 'success')
  } catch (error) {
    store.notify('演示素材载入失败', error.message, 'error')
  }
}

async function submitVideo() {
  const input = videoFileInput.value
  if (!input?.files?.length) return
  const form = new FormData()
  form.append('file', input.files[0])
  if (videoCameraId.value) form.append('camera_id', videoCameraId.value)
  videoBusy.value = true
  job.value = { id: '', status: 'queued', progress: 0, error: '' }
  try {
    const created = await api.inferVideo(form)
    job.value.id = created.job_id
    store.notify('视频任务已创建', '系统将在后台逐帧检测并生成结果视频', 'info')
    pollJob(created.job_id)
  } catch (error) {
    job.value.status = 'failed'
    job.value.error = error.message
    store.notify('视频任务失败', error.message, 'error')
  } finally {
    videoBusy.value = false
  }
}

function pollJob(jobId) {
  clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    try {
      const current = await api.listJobs({})
      const found = current.find((item) => item.job_id === jobId)
      if (!found) return
      job.value = {
        id: found.job_id,
        status: found.status,
        progress: Math.max(0, Math.min(100, Number(found.progress || 0))),
        error: found.error_message || ''
      }
      if (['queued', 'running'].includes(found.status)) {
        pollJob(jobId)
        return
      }
      if (found.status === 'completed') {
        store.notify('视频分析完成', '结果文件和安全事件已经生成', 'success')
      } else {
        store.notify('视频分析失败', found.error_message || '请检查视频格式和模型状态', 'error')
      }
      await Promise.all([store.refreshMetrics(), store.refreshEvents(), store.refreshJobs()])
    } catch (error) {
      store.notify('任务轮询中断', error.message, 'error')
    }
  }, 1200)
}

onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <section>
    <div class="page-intro">
      <div><span class="section-label">AI INFERENCE WORKSPACE</span><h2>智能检测中心</h2><p>上传现场图片或视频，系统自动识别人员、PPE 穿戴与危险区域事件。</p></div>
      <div class="step-flow"><span class="active">1 上传素材</span><i>→</i><span>2 AI 推理</span><i>→</i><span>3 事件判定</span></div>
    </div>

    <div class="detection-grid">
      <article class="panel image-workbench">
        <div class="panel-heading">
          <div><span class="section-label">IMAGE INFERENCE</span><h3>图片安全检测</h3></div>
          <el-select v-model="imageCameraId" placeholder="未绑定监控点" size="small" style="width:170px" clearable>
            <el-option label="未绑定监控点" value="" />
            <el-option v-for="camera in store.cameras" :key="camera.id" :label="camera.name" :value="String(camera.id)" />
          </el-select>
        </div>
        <div id="imageForm">
          <label class="drop-zone" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="onImageDrop">
            <input ref="imageFileInput" type="file" accept="image/*" @change="onImagePick" />
            <span class="upload-icon">↑</span>
            <strong>拖拽现场图片到此处</strong>
            <small>或点击选择 JPG、PNG、WEBP 图片</small>
            <em>{{ imageFileName || '单文件最大 100 MB' }}</em>
          </label>
          <div class="demo-picker">
            <label><span>快速载入演示素材</span>
              <el-select v-model="imageDemoAsset" placeholder="选择内置演示素材" size="small">
                <el-option v-for="asset in imageDemoOptions" :key="asset.asset_id" :label="`${asset.name}${asset.size ? ` · ${asset.size}` : ''}`" :value="asset.asset_id" />
              </el-select>
            </label>
            <button class="outline-button" type="button" @click="loadImageDemo">载入图片样例</button>
          </div>
          <button class="primary full-button" type="button" :disabled="imageBusy" @click="submitImage"><span>◉</span> {{ imageBusy ? 'AI 推理中' : '开始智能检测' }}</button>
        </div>
        <div class="inference-stage">
          <img v-if="previewUrl" :src="previewUrl" class="preview" style="display:block" alt="检测结果预览" />
          <div v-else class="stage-placeholder"><span class="scan-frame"></span><strong>检测画面将在此显示</strong><small>识别框、置信度和违规证据同步标注</small></div>
          <div class="scanning-line" :class="{ active: imageBusy }"></div>
        </div>
      </article>

      <article class="panel result-panel">
        <div class="panel-heading">
          <div><span class="section-label">DETECTION RESULT</span><h3>结构化检测结果</h3></div>
          <span class="state-chip" :class="imageState">{{ { idle: '等待任务', running: 'AI 推理中', success: '检测完成', error: '检测失败' }[imageState] }}</span>
        </div>
        <div class="result-metrics">
          <div><span>检测目标</span><strong>{{ detectionCounts.total }}</strong></div>
          <div><span>人员</span><strong>{{ detectionCounts.person }}</strong></div>
          <div><span>安全帽</span><strong>{{ detectionCounts.helmet }}</strong></div>
          <div><span>反光背心</span><strong>{{ detectionCounts.vest }}</strong></div>
        </div>
        <div class="result-alert" :class="imageAlert.cls">
          <span>{{ imageAlert.icon }}</span>
          <div><strong>{{ imageAlert.title }}</strong><p>{{ imageAlert.text }}</p></div>
        </div>
        <div class="detection-table-wrap">
          <el-table :data="imageResult?.detections || []" size="small" style="width:100%">
            <el-table-column label="类别">
              <template #default="{ row }">
                <div class="class-cell"><span class="class-icon">◉</span>{{ classLabel(row.class_name) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="110">
              <template #default="{ row }"><span class="confidence">{{ (Number(row.confidence || 0) * 100).toFixed(1) }}%</span></template>
            </el-table-column>
            <el-table-column label="轨迹 ID" width="90">
              <template #default="{ row }">{{ row.track_id ?? '--' }}</template>
            </el-table-column>
          </el-table>
        </div>
        <details class="raw-result">
          <summary>查看原始 JSON 数据</summary>
          <pre class="json-view">{{ imageResult ? JSON.stringify(imageResult, null, 2) : '等待上传' }}</pre>
        </details>
      </article>
    </div>

    <article class="panel video-workbench">
      <div class="panel-heading">
        <div><span class="section-label">VIDEO JOB</span><h3>视频异步分析任务</h3></div>
        <el-select v-model="videoCameraId" placeholder="未绑定监控点" size="small" style="width:170px" clearable>
          <el-option label="未绑定监控点" value="" />
          <el-option v-for="camera in store.cameras" :key="camera.id" :label="camera.name" :value="String(camera.id)" />
        </el-select>
      </div>
      <div class="video-layout">
        <form class="video-upload" @submit.prevent="submitVideo">
          <label>
            <span>选择现场视频</span>
            <input ref="videoFileInput" type="file" accept="video/*" @change="onVideoPick" />
            <em>{{ videoFileName || '支持 MP4、AVI、MOV、MKV，单文件最大 100 MB' }}</em>
          </label>
          <div class="demo-picker">
            <label><span>快速载入演示素材</span>
              <el-select v-model="videoDemoAsset" placeholder="选择内置演示素材" size="small">
                <el-option v-for="asset in videoDemoOptions" :key="asset.asset_id" :label="`${asset.name}${asset.size ? ` · ${asset.size}` : ''}`" :value="asset.asset_id" />
              </el-select>
            </label>
            <button class="outline-button" type="button" @click="loadVideoDemo">载入视频样例</button>
          </div>
          <button class="primary" type="submit" :disabled="videoBusy">提交视频任务</button>
        </form>
        <div class="job-console">
          <div class="job-icon">▶</div>
          <div class="job-main">
            <div><strong>{{ JOB_STATUS_TEXT[job.status] || '暂无视频任务' }}</strong><span>{{ job.progress.toFixed(1) }}%</span></div>
            <div class="progress-track"><i :style="{ width: `${Math.max(job.progress, job.status === 'queued' ? 2 : 0)}%` }"></i></div>
            <small>{{ job.error || (job.id ? `任务 ID：${job.id}` : '提交后自动轮询任务状态') }}</small>
          </div>
          <button v-if="job.status === 'completed'" class="outline-button" type="button" @click="store.openJobResult(job.id)">查看可视化结果</button>
        </div>
      </div>
    </article>
  </section>
</template>
