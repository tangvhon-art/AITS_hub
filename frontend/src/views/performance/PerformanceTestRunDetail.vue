<template>
  <div class="perf-run-detail">
    <div class="page-header">
      <a-button @click="$router.back()"><ArrowLeftOutlined /> 返回</a-button>
      <h2>执行结果详情</h2>
      <a-button @click="loadData" :loading="loading"><ReloadOutlined /> 刷新</a-button>
    </div>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="4"><a-card><a-statistic title="总请求数" :value="run.total_requests" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="失败数" :value="run.total_failures || 0" :value-style="{ color: (run.total_failures || 0) > 0 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="失败率" :value="run.failure_rate || 0" suffix="%" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="RPS" :value="run.requests_per_second || 0" :precision="1" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="平均响应" :value="run.avg_response_time || 0" :precision="1" suffix="ms" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="P95响应" :value="run.p95_response_time || 0" :precision="1" suffix="ms" :value-style="{ color: (run.p95_response_time || 0) > 1000 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
    </a-row>

    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="响应时间趋势">
          <div ref="responseChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="性能指标汇总">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="状态"><a-tag :color="statusColor(run.status)">{{ statusText(run.status) }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ run.started_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="结束时间">{{ run.finished_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="最小响应">{{ run.min_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="最大响应">{{ run.max_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P50响应">{{ run.p50_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P95响应">{{ run.p95_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P99响应">{{ run.p99_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
    </a-row>

    <a-card v-if="run.error_summary && Object.keys(run.error_summary).length > 0" title="错误汇总" style="margin-top: 16px">
      <a-table :columns="errorColumns" :data-source="errorData" :pagination="false" row-key="error" size="small" />
    </a-card>

    <a-card title="执行记录列表" style="margin-top: 16px">
      <a-table :columns="runColumns" :data-source="runs" :loading="loading" :pagination="runPagination" row-key="id" size="small" @change="handleRunTableChange">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-button size="small" type="link" @click="viewRun(record)">详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import { performanceTestsApi, type PerformanceTestRun } from '@/api/performanceTests'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const testId = Number(route.params.testId)

const loading = ref(false)
const run = ref<Partial<PerformanceTestRun>>({})
const runs = ref<PerformanceTestRun[]>([])
const runPagination = ref({ current: 1, pageSize: 10, total: 0 })
const responseChartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const runColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '状态', key: 'status', width: 100 },
  { title: '总请求', dataIndex: 'total_requests', key: 'total_requests', width: 90 },
  { title: '失败数', dataIndex: 'total_failures', key: 'total_failures', width: 80 },
  { title: 'RPS', dataIndex: 'requests_per_second', key: 'requests_per_second', width: 80 },
  { title: 'P95(ms)', dataIndex: 'p95_response_time', key: 'p95_response_time', width: 90 },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at', width: 180 },
  { title: '操作', key: 'action', width: 80 },
]

const errorColumns = [
  { title: '错误信息', dataIndex: 'error', key: 'error', ellipsis: true },
  { title: '次数', dataIndex: 'count', key: 'count', width: 100 },
]

const errorData = ref<any[]>([])

const statusColor = (s?: string) => ({ pending: 'default', running: 'processing', completed: 'success', failed: 'error', stopped: 'warning' })[s || ''] || 'default'
const statusText = (s?: string) => ({ pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' })[s || ''] || s || '-'

async function loadData() {
  loading.value = true
  try {
    const [runRes, runsRes] = await Promise.all([
      performanceTestsApi.listRuns(projectId, testId, { page: 1, page_size: 1 }),
      performanceTestsApi.listRuns(projectId, testId, {
        page: runPagination.value.current,
        page_size: runPagination.value.pageSize,
      }),
    ])
    if (runRes.items.length > 0) {
      run.value = runRes.items[0]
      errorData.value = Object.entries(run.value.error_summary || {}).map(([error, count]) => ({ error, count }))
      await nextTick()
      renderChart()
    }
    runs.value = runsRes.items
    runPagination.value.total = runsRes.total
    startPollingIfNeeded()
  } catch { } finally {
    loading.value = false
  }
}

function startPollingIfNeeded() {
  stopPolling()
  const status = run.value.status
  if (status === 'pending' || status === 'running') {
    pollTimer = setInterval(async () => {
      try {
        if (run.value.id) {
          const detail = await performanceTestsApi.getRun(run.value.id)
          run.value = detail
          errorData.value = Object.entries(detail.error_summary || {}).map(([error, count]) => ({ error, count }))
          await nextTick()
          renderChart()
          if (detail.status !== 'pending' && detail.status !== 'running') {
            stopPolling()
            loadData()
          }
        }
      } catch { }
    }, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function viewRun(record: PerformanceTestRun) {
  try {
    const detail = await performanceTestsApi.getRun(record.id)
    run.value = detail
    errorData.value = Object.entries(detail.error_summary || {}).map(([error, count]) => ({ error, count }))
    await nextTick()
    renderChart()
  } catch { }
}

function handleRunTableChange(p: any) {
  runPagination.value.current = p.current
  runPagination.value.pageSize = p.pageSize
  loadData()
}

function renderChart() {
  if (!responseChartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(responseChartRef.value)
  }

  const history = run.value.stats_history || []
  const categories = history.map((_, i) => `${i + 1}s`)
  const p50Data = history.map((h: any) => h.p50 || 0)
  const p95Data = history.map((h: any) => h.p95 || 0)
  const p99Data = history.map((h: any) => h.p99 || 0)
  const rpsData = history.map((h: any) => h.rps || 0)

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['P50', 'P95', 'P99', 'RPS'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: categories },
    yAxis: [
      { type: 'value', name: 'ms', position: 'left' },
      { type: 'value', name: 'RPS', position: 'right' },
    ],
    series: [
      { name: 'P50', type: 'line', data: p50Data, smooth: true },
      { name: 'P95', type: 'line', data: p95Data, smooth: true },
      { name: 'P99', type: 'line', data: p99Data, smooth: true },
      { name: 'RPS', type: 'line', data: rpsData, smooth: true, yAxisIndex: 1, lineStyle: { type: 'dashed' } },
    ],
  })
}

onMounted(() => loadData())
onUnmounted(() => {
  stopPolling()
  chartInstance?.dispose()
})
</script>

<style scoped>
.perf-run-detail { padding: 0; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.page-header h2 { margin: 0; flex: 1; }
.chart-container { height: 300px; }
</style>
