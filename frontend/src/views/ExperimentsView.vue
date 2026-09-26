<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useAppStore } from '../store'
import { formatMetric } from '../utils'

const store = useAppStore()
const chartRef = ref(null)
let chart = null

const summary = computed(() => store.experimentSummary)
const splits = computed(() => summary.value?.splits || {})
const datasetTotals = computed(() => {
  const totalImages = ['train', 'val', 'test'].reduce((sum, key) => sum + Number(splits.value?.[key]?.images || 0), 0)
  const totalBoxes = ['train', 'val', 'test'].reduce((sum, key) => sum + Number(splits.value?.[key]?.boxes || 0), 0)
  return { images: totalImages, boxes: totalBoxes }
})

const datasetCards = computed(() => [
  ['类别数', summary.value?.classes?.length ?? 0],
  ['训练集图片', splits.value?.train?.images ?? 0],
  ['验证集图片', splits.value?.val?.images ?? 0],
  ['测试集图片', splits.value?.test?.images ?? 0],
  ['总图片', datasetTotals.value.images],
  ['总标注框', datasetTotals.value.boxes]
])

const preferred = computed(() => {
  const models = summary.value?.models || []
  return (
    models.find((model) => model.is_current) ||
    models.find((model) => String(model.model_name || '').toLowerCase().includes('hard cases')) ||
    models.find((model) => (model.dataset_name || '').startsWith('Expanded PPE')) ||
    models.find((model) => model.model_name === 'YOLOv8s') ||
    models[0]
  )
})

const preferredTitle = computed(() => {
  const model = preferred.value
  if (!model) return '模型分项指标'
  return model.is_current ? 'E7 当前部署分项指标' : `${model.model_name} 分项指标`
})

function shortModelName(name) {
  return String(name || '')
    .replace('YOLOv8s (', '')
    .replace('YOLOv8n', 'v8n')
    .replace(')', '')
    .slice(0, 22)
}

function renderChart() {
  if (!chart) return
  const models = (summary.value?.models || []).filter((model) => model.precision !== null && model.precision !== undefined).slice(0, 8)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Precision', 'Recall', 'F1', 'mAP@0.5'], textStyle: { fontSize: 10, color: '#718295' }, top: 0 },
    grid: { left: 40, right: 16, top: 34, bottom: 60 },
    xAxis: { type: 'category', data: models.map((model) => shortModelName(model.model_name)), axisLabel: { interval: 0, rotate: 28, color: '#718295', fontSize: 9 }, axisLine: { lineStyle: { color: '#dfe7ee' } } },
    yAxis: { type: 'value', max: 1, splitLine: { lineStyle: { color: '#eef2f6' } }, axisLabel: { color: '#718295', fontSize: 10 } },
    series: [
      { name: 'Precision', type: 'bar', barMaxWidth: 14, itemStyle: { color: '#1477ff', borderRadius: [3, 3, 0, 0] }, data: models.map((model) => model.precision) },
      { name: 'Recall', type: 'bar', barMaxWidth: 14, itemStyle: { color: '#00c2ff', borderRadius: [3, 3, 0, 0] }, data: models.map((model) => model.recall) },
      { name: 'F1', type: 'bar', barMaxWidth: 14, itemStyle: { color: '#7c5cff', borderRadius: [3, 3, 0, 0] }, data: models.map((model) => model.f1) },
      { name: 'mAP@0.5', type: 'bar', barMaxWidth: 14, itemStyle: { color: '#0abf87', borderRadius: [3, 3, 0, 0] }, data: models.map((model) => model.map50) }
    ]
  })
}

function handleResize() {
  chart?.resize()
}

onMounted(async () => {
  chart = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)
  if (store.token) await store.refreshExperiments()
  renderChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<template>
  <section>
    <div class="page-intro">
      <div><span class="section-label">MODEL &amp; DATA LAB</span><h2>模型实验与数据质量</h2><p>展示真实评估产物、模型对比和数据集划分，支持论文与答辩追溯。</p></div>
      <button class="outline-button" type="button" @click="store.refreshExperiments()">↻ 刷新实验</button>
    </div>

    <article class="panel experiment-overview-panel">
      <div class="panel-heading"><div><span class="section-label">DATASET PROFILE</span><h3>{{ summary?.dataset_name || 'Expanded PPE' }}</h3></div><span class="period-tag">{{ summary?.dataset_version ? `数据记录 ${new Date(summary.dataset_version).toLocaleDateString('zh-CN')}` : '版本未记录' }}</span></div>
      <div class="dataset-meta">
        <div v-for="[label, value] in datasetCards" :key="label"><span>{{ label }}</span><strong>{{ value }}</strong></div>
      </div>
    </article>

    <article class="panel" style="margin-bottom:14px">
      <div class="panel-heading"><div><span class="section-label">BENCHMARK CHART</span><h3>模型指标对比图</h3></div><span class="period-tag">仅含已产出 test 指标的模型</span></div>
      <div ref="chartRef" style="width:100%;height:300px;padding:10px 12px;box-sizing:border-box"></div>
    </article>

    <div class="experiment-grid">
      <article class="panel">
        <div class="panel-heading"><div><span class="section-label">MODEL BENCHMARK</span><h3>模型指标与数据版本</h3></div></div>
        <div class="table-scroll">
          <el-table :data="summary?.models || []" class="experiment-table" size="small" style="width:100%;min-width:700px" :row-class-name="(row) => (row.is_current ? 'current-model-row' : '')">
            <el-table-column label="模型" min-width="230">
              <template #default="{ row }">
                <strong>{{ row.model_name }}</strong>
                <el-tag v-if="row.is_current" size="small" type="success" effect="light" style="margin-left:6px">当前部署</el-tag>
                <br /><small style="color:#9ca8b5">{{ row.dataset_name || '未记录数据版本' }}</small>
              </template>
            </el-table-column>
            <el-table-column label="Precision" width="90"><template #default="{ row }">{{ formatMetric(row.precision) }}</template></el-table-column>
            <el-table-column label="Recall" width="80"><template #default="{ row }">{{ formatMetric(row.recall) }}</template></el-table-column>
            <el-table-column label="F1" width="80"><template #default="{ row }">{{ formatMetric(row.f1) }}</template></el-table-column>
            <el-table-column label="mAP@0.5" width="90"><template #default="{ row }">{{ formatMetric(row.map50) }}</template></el-table-column>
            <el-table-column label="mAP@0.5:0.95" width="110"><template #default="{ row }">{{ formatMetric(row.map50_95) }}</template></el-table-column>
          </el-table>
        </div>
        <p class="experiment-note">{{ summary?.notes || '指标来自项目实际评估结果。' }}</p>
      </article>

      <article class="panel">
        <div class="panel-heading"><div><span class="section-label">DATA QUALITY</span><h3>数据集划分校验</h3></div></div>
        <div class="split-list">
          <div v-for="name in ['train', 'val', 'test']" :key="name" class="split-row">
            <div>
              <strong>{{ name.toUpperCase() }}</strong>
              <span>{{ splits[name]?.images ?? 0 }} 张图片 · {{ splits[name]?.labels ?? 0 }} 个标签 · {{ splits[name]?.boxes ?? 0 }} 个框</span>
            </div>
            <b :class="(splits[name]?.errors?.length || 0) ? 'quality-error' : 'quality-ok'">{{ splits[name]?.errors?.length ? `${splits[name].errors.length} 个问题` : '校验通过' }}</b>
          </div>
        </div>
      </article>
    </div>

    <article class="panel class-metrics-panel">
      <div class="panel-heading">
        <div><span class="section-label">PER-CLASS METRICS</span><h3>{{ preferredTitle }}</h3></div>
        <span class="period-tag">{{ preferred?.is_current ? '当前部署 · test split' : 'test split' }}</span>
      </div>
      <div class="table-scroll">
        <el-table :data="Object.entries(preferred?.per_class || {}).map(([name, metric]) => ({ name, ...metric }))" size="small" style="width:100%;min-width:620px">
          <el-table-column label="类别" min-width="160">
            <template #default="{ row }"><strong>{{ row.name }}</strong></template>
          </el-table-column>
          <el-table-column label="Precision" width="110"><template #default="{ row }">{{ formatMetric(row.precision) }}</template></el-table-column>
          <el-table-column label="Recall" width="100"><template #default="{ row }">{{ formatMetric(row.recall) }}</template></el-table-column>
          <el-table-column label="F1" width="100"><template #default="{ row }">{{ formatMetric(row.f1) }}</template></el-table-column>
          <el-table-column label="AP@0.5" width="100"><template #default="{ row }">{{ formatMetric(row.map50) }}</template></el-table-column>
        </el-table>
      </div>
    </article>
  </section>
</template>
