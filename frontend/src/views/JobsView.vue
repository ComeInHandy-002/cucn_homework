<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAppStore } from '../store'
import { formatDateTime, JOB_SOURCE_LABELS, JOB_STATUS_LABELS } from '../utils'

const store = useAppStore()

const statusFilter = ref('')
const sourceFilter = ref('')

const counts = computed(() =>
  store.jobs.reduce(
    (result, job) => {
      result.total += 1
      if (['queued', 'running'].includes(job.status)) result.running += 1
      if (job.status === 'completed') result.completed += 1
      if (job.status === 'failed') result.failed += 1
      return result
    },
    { total: 0, running: 0, completed: 0, failed: 0 }
  )
)

const summaryCards = computed(() => [
  { cls: 'info', icon: 'Σ', label: '任务总数', value: counts.value.total, note: '当前账户可见记录' },
  { cls: 'warning', icon: '⌛', label: '执行中', value: counts.value.running, note: '排队或正在处理' },
  { cls: 'success', icon: '✓', label: '已完成', value: counts.value.completed, note: '可查看结果文件' },
  { cls: 'danger', icon: '!', label: '失败任务', value: counts.value.failed, note: '需要检查错误信息' }
])

async function refresh() {
  const query = { limit: '100' }
  if (statusFilter.value) query.status = statusFilter.value
  if (sourceFilter.value) query.source_type = sourceFilter.value
  await store.refreshJobs()
}

onMounted(() => {
  if (store.token) store.refreshJobs()
})
</script>

<template>
  <section>
    <div class="page-intro">
      <div><span class="section-label">INFERENCE JOB CENTER</span><h2>推理任务中心</h2><p>统一查看图片与视频任务的提交时间、执行进度和结果文件。</p></div>
      <button class="outline-button" type="button" @click="store.refreshJobs()">↻ 刷新任务</button>
    </div>

    <section class="job-summary-grid">
      <article v-for="card in summaryCards" :key="card.label" class="metric-card" :class="card.cls">
        <div class="metric-icon">{{ card.icon }}</div>
        <div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div>
      </article>
    </section>

    <article class="panel job-history-panel">
      <div class="filter-bar">
        <div><span class="section-label">JOB HISTORY</span><h3>任务执行记录</h3></div>
        <div class="filter-actions">
          <el-select v-model="statusFilter" placeholder="全部状态" size="small" style="width:130px" @change="refresh">
            <el-option label="全部状态" value="" />
            <el-option v-for="(label, key) in JOB_STATUS_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
          <el-select v-model="sourceFilter" placeholder="全部类型" size="small" style="width:130px" @change="refresh">
            <el-option label="全部类型" value="" />
            <el-option v-for="(label, key) in JOB_SOURCE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </div>
      </div>
      <div class="table-scroll">
        <el-table :data="store.jobs" class="job-table" size="small" style="width:100%;min-width:900px">
          <el-table-column label="提交时间" width="120">
            <template #default="{ row }">
              <strong>{{ formatDateTime(row.created_at).time }}</strong><br /><small style="color:#9ca8b5">{{ formatDateTime(row.created_at).date }}</small>
            </template>
          </el-table-column>
          <el-table-column label="任务类型" width="90">
            <template #default="{ row }">{{ JOB_SOURCE_LABELS[row.source_type] || row.source_type || '未知' }}</template>
          </el-table-column>
          <el-table-column label="任务 ID" width="160">
            <template #default="{ row }"><code class="job-id">{{ row.job_id }}</code></template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><span class="status-badge" :class="row.status">{{ JOB_STATUS_LABELS[row.status] || row.status }}</span></template>
          </el-table-column>
          <el-table-column label="进度" width="150">
            <template #default="{ row }">
              <div class="job-progress"><i :style="{ width: `${Math.max(0, Math.min(100, Number(row.progress || 0)))}%` }"></i></div>
              <small>{{ Number(row.progress || 0).toFixed(1) }}%</small>
            </template>
          </el-table-column>
          <el-table-column label="结果">
            <template #default="{ row }">
              <button v-if="row.result_path" class="text-button" type="button" @click="store.openJobResult(row.job_id)">查看可视化结果</button>
              <span v-else-if="row.error_message" class="no-evidence" :title="row.error_message">错误详情</span>
              <span v-else class="no-evidence">处理中</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="table-footer"><span>共 {{ store.jobs.length }} 条任务</span><small>图片任务即时完成，视频任务后台处理</small></div>
    </article>
  </section>
</template>
