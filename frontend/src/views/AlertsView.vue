<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAppStore } from '../store'
import { listEvents } from '../api'
import { eventIcon, eventLabel, formatDateTime, SEVERITY_LABELS, STATUS_LABELS } from '../utils'

const store = useAppStore()

const statusTab = ref('')
const typeFilter = ref('')

async function refresh() {
  const query = { limit: '100' }
  if (statusTab.value) query.status = statusTab.value
  if (typeFilter.value) query.event_type = typeFilter.value
  store.events = await listEvents(query)
}

async function handleStatus(eventId, status) {
  try {
    await store.updateEventStatus(eventId, status)
  } catch (error) {
    store.notify('事件处理失败', error.message, 'error')
  }
}

function showEvidence(event) {
  if (event.evidence_path) store.evidenceEvent = event
}

const statusTabs = [
  { value: '', label: '全部' },
  { value: 'open', label: '待处理' },
  { value: 'acknowledged', label: '已确认' },
  { value: 'resolved', label: '已关闭' }
]

const rows = computed(() => store.events)
onMounted(() => {
  if (store.token) store.refreshEvents()
})
</script>

<template>
  <section>
    <div class="page-intro">
      <div><span class="section-label">SAFETY EVENT CENTER</span><h2>告警事件中心</h2><p>集中查看违规证据，完成人工确认与闭环处理。</p></div>
      <div class="live-indicator"><i></i><span>WebSocket 实时接收</span></div>
    </div>

    <article class="panel alert-workbench">
      <div class="filter-bar">
        <div class="filter-tabs">
          <button v-for="tab in statusTabs" :key="tab.value" type="button" :class="{ active: statusTab === tab.value }" @click="statusTab = tab.value; refresh()">{{ tab.label }}</button>
        </div>
        <div class="filter-actions">
          <el-select v-model="typeFilter" placeholder="全部事件类型" size="small" style="width:150px" @change="refresh">
            <el-option label="全部事件类型" value="" />
            <el-option label="未佩戴安全帽" value="no_helmet" />
            <el-option label="未穿反光背心" value="no_vest" />
            <el-option label="危险区域闯入" value="intrusion" />
          </el-select>
          <button class="outline-button" type="button" @click="refresh">↻ 刷新数据</button>
        </div>
      </div>
      <div class="table-scroll">
        <el-table :data="rows" class="event-table" size="small" style="width:100%;min-width:880px">
          <el-table-column label="发生时间" width="120">
            <template #default="{ row }">
              <strong>{{ formatDateTime(row.timestamp).time }}</strong><br /><small style="color:#9ca8b5">{{ formatDateTime(row.timestamp).date }}</small>
            </template>
          </el-table-column>
          <el-table-column label="安全事件" min-width="200">
            <template #default="{ row }">
              <div class="event-name">
                <span class="event-name-icon">{{ eventIcon(row.event_type) }}</span>
                <div><strong>{{ eventLabel(row.event_type) }}</strong><span>{{ row.message || '安全规则触发' }}</span></div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="监控点 / 人员" min-width="140">
            <template #default="{ row }">
              {{ store.cameraName(row.camera_id) }}<br /><small style="color:#9ca8b5">Track ID: {{ row.track_id ?? '--' }}</small>
            </template>
          </el-table-column>
          <el-table-column label="风险等级" width="100">
            <template #default="{ row }"><span class="risk-badge" :class="row.severity">{{ SEVERITY_LABELS[row.severity] || row.severity }}</span></template>
          </el-table-column>
          <el-table-column label="处理状态" width="100">
            <template #default="{ row }"><span class="status-badge" :class="row.status">{{ STATUS_LABELS[row.status] || row.status }}</span></template>
          </el-table-column>
          <el-table-column label="证据" width="110">
            <template #default="{ row }">
              <button v-if="row.evidence_path" class="evidence-button" type="button" @click="showEvidence(row)">查看截图</button>
              <span v-else class="no-evidence">暂无证据</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <span v-if="row.status === 'resolved'" class="no-evidence">已闭环</span>
              <div v-else class="actions">
                <button v-if="row.status === 'open'" type="button" @click="handleStatus(row.id, 'acknowledged')">确认</button>
                <button type="button" @click="handleStatus(row.id, 'resolved')">关闭</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="table-footer"><span>共 {{ rows.length }} 条安全事件</span><small>事件按发生时间倒序排列</small></div>
    </article>
  </section>
</template>
