<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { adminApi, isAdminLoggedIn } from '../adminApi'
import AdminGate from '../components/AdminGate.vue'

const datasets = ref([])
const tasks = ref([])
const loading = ref(false)
const uploadInput = ref(null)
const uploadForm = reactive({ name: '', note: '' })
const uploading = ref(false)
const training = ref(false)
let pollTimer = null

const STATUS_META = {
  pending: { label: '排队中', type: 'info' },
  running: { label: '训练中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' }
}

const latestMetrics = computed(() => {
  const done = tasks.value.find((task) => task.status === 'completed' && task.metricsJson)
  if (!done) return null
  try {
    return { task: done, metrics: JSON.parse(done.metricsJson) }
  } catch {
    return null
  }
})

async function refresh() {
  loading.value = true
  try {
    datasets.value = await adminApi.listDatasets()
    tasks.value = await adminApi.listTrainingTasks()
    schedulePoll()
  } finally {
    loading.value = false
  }
}

function schedulePoll() {
  clearTimeout(pollTimer)
  if (tasks.value.some((task) => task.status === 'pending' || task.status === 'running')) {
    pollTimer = setTimeout(async () => {
      tasks.value = await adminApi.listTrainingTasks()
      schedulePoll()
    }, 5000)
  }
}

async function submitUpload() {
  const input = uploadInput.value
  if (!input?.files?.length) return
  uploading.value = true
  try {
    await adminApi.uploadDataset(input.files[0], uploadForm.name, uploadForm.note)
    uploadForm.name = ''
    uploadForm.note = ''
    input.value = ''
    await refresh()
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

async function startTraining() {
  training.value = true
  try {
    await adminApi.startTraining(`管理端训练-${new Date().toLocaleString('zh-CN', { hour12: false })}`, 'construction-ppe')
    await refresh()
  } catch {
    // 拦截器已提示
  } finally {
    training.value = false
  }
}

async function removeDataset(dataset) {
  try {
    await adminApi.deleteDataset(dataset.id)
    await refresh()
  } catch {
    // 拦截器已提示
  }
}

function formatSize(bytes) {
  if (!bytes) return '--'
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(1)} KB`
}

onMounted(async () => {
  if (isAdminLoggedIn()) await refresh()
})

onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <AdminGate title="数据集与模型管理" @logged-in="refresh">
  <section>
    <div class="page-intro">
      <div><span class="section-label">DATASET &amp; MODEL OPS</span><h2>数据集与模型管理</h2><p>上传数据集、发起演示级在线训练（真实 YOLOv8 1 epoch 任务）、查看评估指标。</p></div>
      <button class="outline-button" type="button" @click="refresh">↻ 刷新</button>
    </div>

    <div class="detection-grid" style="grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)">
      <article class="panel">
        <div class="panel-heading"><div><span class="section-label">DATASETS</span><h3>数据集管理</h3></div><span class="count-tag">{{ datasets.length }} 个</span></div>
        <div style="padding: 14px 18px; display: grid; gap: 10px">
          <label style="display: grid; gap: 6px"><span style="color:#64788b;font-size:11px">选择数据集压缩包</span>
            <input ref="uploadInput" type="file" accept=".zip,.rar,.7z,.tar.gz" />
          </label>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
            <input v-model="uploadForm.name" placeholder="数据集名称（可选）" style="padding: 8px 10px; border: 1px solid #dce5ec; border-radius: 7px; font-size: 11px" />
            <input v-model="uploadForm.note" placeholder="备注（可选）" style="padding: 8px 10px; border: 1px solid #dce5ec; border-radius: 7px; font-size: 11px" />
          </div>
          <button class="primary" type="button" :disabled="uploading" @click="submitUpload">{{ uploading ? '上传中...' : '上传数据集' }}</button>
        </div>
        <div class="table-scroll">
          <el-table :data="datasets" size="small" style="width:100%">
            <el-table-column label="名称" min-width="140">
              <template #default="{ row }"><strong>{{ row.name }}</strong><br /><small style="color:#9ca8b5">{{ row.originalFilename }}</small></template>
            </el-table-column>
            <el-table-column label="大小" width="90">
              <template #default="{ row }">{{ formatSize(row.sizeBytes) }}</template>
            </el-table-column>
            <el-table-column label="SHA256" width="120">
              <template #default="{ row }"><code class="job-id" :title="row.sha256">{{ row.sha256?.slice(0, 12) || '--' }}…</code></template>
            </el-table-column>
            <el-table-column label="上传时间" width="110">
              <template #default="{ row }">{{ row.uploadedAt?.slice(0, 10) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <button class="icon-text-button danger-text" type="button" @click="removeDataset(row)">删除</button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </article>

      <article class="panel">
        <div class="panel-heading">
          <div><span class="section-label">ONLINE TRAINING</span><h3>模型在线训练与评估</h3></div>
          <button class="primary compact-button" type="button" :disabled="training" @click="startTraining">{{ training ? '提交中...' : '▶ 发起演示训练' }}</button>
        </div>
        <div v-if="latestMetrics" style="margin: 14px 18px; padding: 12px; border: 1px solid #d6e6f8; border-radius: 8px; background: #f4f9ff">
          <strong style="font-size: 11px">最近一次训练真实指标（{{ latestMetrics.task.name }}）</strong>
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 8px">
            <div class="job-result-stat"><span>epoch</span><strong>{{ latestMetrics.metrics.final_epoch }}</strong></div>
            <div class="job-result-stat"><span>Precision</span><strong>{{ Number(latestMetrics.metrics.precision || 0).toFixed(4) }}</strong></div>
            <div class="job-result-stat"><span>Recall</span><strong>{{ Number(latestMetrics.metrics.recall || 0).toFixed(4) }}</strong></div>
            <div class="job-result-stat"><span>mAP@0.5</span><strong>{{ Number(latestMetrics.metrics.mAP50 || 0).toFixed(4) }}</strong></div>
          </div>
        </div>
        <div class="table-scroll">
          <el-table :data="tasks" size="small" style="width:100%">
            <el-table-column label="任务" min-width="150">
              <template #default="{ row }"><strong>{{ row.name }}</strong><br /><small style="color:#9ca8b5">{{ row.datasetTag || '--' }} · {{ row.epochs }} epoch</small></template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="STATUS_META[row.status]?.type || 'info'" effect="light" size="small">{{ STATUS_META[row.status]?.label || row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="110">
              <template #default="{ row }">{{ row.createdAt?.slice(5, 16).replace('T', ' ') }}</template>
            </el-table-column>
            <el-table-column label="说明" min-width="140">
              <template #default="{ row }">
                <small v-if="row.status === 'failed'" style="color:#c92c52">{{ row.errorMessage }}</small>
                <small v-else-if="row.status === 'completed'" style="color:#168265">权重与评估产物已生成</small>
                <small v-else style="color:#9ca8b5">异步执行中，页面自动轮询</small>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </article>
    </div>
  </section>
  </AdminGate>
</template>
