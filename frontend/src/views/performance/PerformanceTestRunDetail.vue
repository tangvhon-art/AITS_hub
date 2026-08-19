<template>
  <div class="perf-run-detail">
    <div class="page-header">
      <a-button @click="$router.back()"><ArrowLeftOutlined /> 返回</a-button>
      <h2>执行结果详情</h2>
      <div class="header-actions">
        <a-button @click="loadData" :loading="loading"><ReloadOutlined /> 刷新</a-button>
        <a-button
          type="primary"
          :loading="analyzing"
          :disabled="run.status !== 'completed'"
          @click="handleAnalyze"
        >
          <RobotOutlined /> AI 性能分析
        </a-button>
      </div>
    </div>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="4"><a-card><a-statistic title="总请求数" :value="run.total_requests" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="失败数" :value="run.total_failures || 0" :value-style="{ color: (run.total_failures || 0) > 0 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="失败率" :value="run.failure_rate || 0" suffix="%" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="RPS" :value="run.requests_per_second || 0" :precision="1" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="平均响应" :value="run.avg_response_time || 0" :precision="1" suffix="ms" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="P95响应" :value="run.p95_response_time || 0" :precision="1" suffix="ms" :value-style="{ color: (run.p95_response_time || 0) > 1000 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
    </a-row>

    <!-- JMeter 风格聚合报告 -->
    <a-card v-if="endpointStats.length > 0" title="聚合报告（JMeter 风格）" style="margin-bottom: 16px">
      <a-table :columns="aggregateColumns" :data-source="endpointStats" :pagination="false" row-key="label" size="small" :scroll="{ x: 1400 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'error_pct'">
            <span :style="{ color: record.error_pct > 0 ? '#cf1322' : '#3f8600' }">{{ record.error_pct }}%</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="响应时间趋势">
          <div v-if="hasTrendData" ref="responseChartRef" class="chart-container"></div>
          <a-empty v-else :description="trendEmptyText" class="chart-empty" />
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
      <a-table
        :columns="runColumns"
        :data-source="runs"
        :loading="loading"
        :pagination="runPagination"
        row-key="id"
        size="small"
        :row-class-name="rowClassName"
        @change="handleRunTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" type="link" :loading="runLoading && selectedRunId === record.id" @click="viewRun(record)">详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 执行记录详情抽屉 -->
    <a-drawer
      v-model:open="showDetailDrawer"
      title="执行记录详情"
      placement="right"
      width="720"
      @after-open="renderDetailChart"
    >
      <template v-if="detailRun.id">
        <a-row :gutter="12" style="margin-bottom: 16px">
          <a-col :span="8"><a-card size="small"><a-statistic title="总请求数" :value="detailRun.total_requests" /></a-card></a-col>
          <a-col :span="8"><a-card size="small"><a-statistic title="失败数" :value="detailRun.total_failures || 0" :value-style="{ color: (detailRun.total_failures || 0) > 0 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
          <a-col :span="8"><a-card size="small"><a-statistic title="失败率" :value="detailRun.failure_rate || 0" suffix="%" /></a-card></a-col>
        </a-row>
        <a-row :gutter="12" style="margin-bottom: 16px">
          <a-col :span="8"><a-card size="small"><a-statistic title="RPS" :value="detailRun.requests_per_second || 0" :precision="1" /></a-card></a-col>
          <a-col :span="8"><a-card size="small"><a-statistic title="平均响应" :value="detailRun.avg_response_time || 0" :precision="1" suffix="ms" /></a-card></a-col>
          <a-col :span="8"><a-card size="small"><a-statistic title="P95响应" :value="detailRun.p95_response_time || 0" :precision="1" suffix="ms" :value-style="{ color: (detailRun.p95_response_time || 0) > 1000 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
        </a-row>

        <a-card title="响应时间趋势" size="small" style="margin-bottom: 16px">
          <div v-if="hasDetailTrendData" ref="detailChartRef" class="chart-container"></div>
          <a-empty v-else :description="detailTrendEmptyText" class="chart-empty" />
        </a-card>

        <a-card title="性能指标汇总" size="small" style="margin-bottom: 16px">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="状态"><a-tag :color="statusColor(detailRun.status)">{{ statusText(detailRun.status) }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ detailRun.started_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="结束时间">{{ detailRun.finished_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="最小响应">{{ detailRun.min_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="最大响应">{{ detailRun.max_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P50响应">{{ detailRun.p50_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P95响应">{{ detailRun.p95_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P99响应">{{ detailRun.p99_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
          </a-descriptions>
        </a-card>

        <a-card v-if="detailErrorData.length > 0" title="错误汇总" size="small">
          <a-table :columns="errorColumns" :data-source="detailErrorData" :pagination="false" row-key="error" size="small" />
        </a-card>
      </template>
      <a-empty v-else description="暂无数据" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import { performanceTestsApi, type PerformanceTestRun } from '@/api/performanceTests'

const route = useRoute()
const projectId = Number(route.params.id)
const testId = Number(route.params.testId)

const loading = ref(false)
const runLoading = ref(false)
const analyzing = ref(false)
const run = ref<Partial<PerformanceTestRun>>({})
const runs = ref<PerformanceTestRun[]>([])
const selectedRunId = ref<number | null>(null)
const runPagination = ref({ current: 1, pageSize: 10, total: 0 })
const responseChartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const showDetailDrawer = ref(false)
const detailRun = ref<Partial<PerformanceTestRun>>({})
const detailErrorData = ref<any[]>([])
const detailChartRef = ref<HTMLElement>()
let detailChartInstance: echarts.ECharts | null = null

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

// 聚合报告（JMeter 风格）
const endpointStats = computed(() => Array.isArray(run.value.endpoint_stats) ? run.value.endpoint_stats : [])
const aggregateColumns = [
  { title: 'Label', dataIndex: 'label', key: 'label', width: 200, fixed: 'left' },
  { title: '#Samples', dataIndex: 'samples', key: 'samples', width: 90 },
  { title: 'Average', dataIndex: 'average', key: 'average', width: 90, sorter: (a: any, b: any) => a.average - b.average },
  { title: 'Min', dataIndex: 'min', key: 'min', width: 80 },
  { title: 'Max', dataIndex: 'max', key: 'max', width: 80 },
  { title: 'Std Dev', dataIndex: 'std_dev', key: 'std_dev', width: 90 },
  { title: 'Error %', key: 'error_pct', width: 90 },
  { title: 'Throughput', dataIndex: 'throughput', key: 'throughput', width: 100 },
  { title: 'Received KB/sec', dataIndex: 'received_kb_s', key: 'received_kb_s', width: 130 },
  { title: 'P50', dataIndex: 'p50', key: 'p50', width: 80 },
  { title: 'P90', dataIndex: 'p90', key: 'p90', width: 80 },
  { title: 'P95', dataIndex: 'p95', key: 'p95', width: 80 },
  { title: 'P99', dataIndex: 'p99', key: 'p99', width: 80 },
]

const statusColor = (s?: string) => ({ pending: 'default', running: 'processing', completed: 'success', failed: 'error', stopped: 'warning' })[s || ''] || 'default'
const statusText = (s?: string) => ({ pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' })[s || ''] || s || '-'

const hasTrendData = computed(() => {
  const h = run.value.stats_history
  if (Array.isArray(h)) return h.length > 0
  if (h && typeof h === 'object') return Array.isArray(h.aggregate) && h.aggregate.length > 0
  return false
})
const trendEmptyText = computed(() => {
  const s = run.value.status
  if (s === 'pending' || s === 'running') return '测试运行中，趋势数据将在测试完成后显示'
  return '暂无趋势数据'
})
const hasDetailTrendData = computed(() => {
  const h = detailRun.value.stats_history
  if (Array.isArray(h)) return h.length > 0
  if (h && typeof h === 'object') return Array.isArray(h.aggregate) && h.aggregate.length > 0
  return false
})
const detailTrendEmptyText = computed(() => {
  const s = detailRun.value.status
  if (s === 'pending' || s === 'running') return '测试运行中，趋势数据将在测试完成后显示'
  return '暂无趋势数据'
})

function rowClassName(record: any) {
  return record.id === selectedRunId.value ? 'selected-run-row' : ''
}

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
      selectedRunId.value = runRes.items[0].id
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
          selectedRunId.value = detail.id
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

async function handleAnalyze() {
  if (!run.value.id) return
  analyzing.value = true
  try {
    await performanceTestsApi.analyze(run.value.id, {})
    message.success('性能分析已启动，完成后将生成性能报告')
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '分析启动失败')
  } finally {
    analyzing.value = false
  }
}

async function viewRun(record: PerformanceTestRun) {
  runLoading.value = true
  selectedRunId.value = record.id
  try {
    const detail = await performanceTestsApi.getRun(record.id)
    detailRun.value = detail
    detailErrorData.value = Object.entries(detail.error_summary || {}).map(([error, count]) => ({ error, count }))
    showDetailDrawer.value = true
  } catch (e: any) {
    message.error('加载详情失败: ' + (e.message || '未知错误'))
  } finally {
    runLoading.value = false
  }
}

function handleRunTableChange(p: any) {
  runPagination.value.current = p.current
  runPagination.value.pageSize = p.pageSize
  loadData()
}

function renderChart() {
  if (!hasTrendData.value) return
  nextTick(() => {
    if (!responseChartRef.value) return
    if (!chartInstance) {
      chartInstance = echarts.init(responseChartRef.value)
    }
    doRenderChart(chartInstance, run.value)
  })
}

function renderDetailChart() {
  nextTick(() => {
    if (!hasDetailTrendData.value) return
    if (!detailChartRef.value) return
    if (!detailChartInstance) {
      detailChartInstance = echarts.init(detailChartRef.value)
    }
    doRenderChart(detailChartInstance, detailRun.value)
  })
}

watch(hasTrendData, (val) => {
  if (val) renderChart()
})
watch(hasDetailTrendData, (val) => {
  if (val) renderDetailChart()
})

function doRenderChart(instance: echarts.ECharts, data: Partial<PerformanceTestRun>) {
  // 兼容新旧格式：旧格式为数组，新格式为 {aggregate: [], by_endpoint: {}}
  const raw = data.stats_history
  const history: any[] = Array.isArray(raw) ? raw : (raw?.aggregate || [])
  const byEndpoint: Record<string, any[]> = raw && !Array.isArray(raw) ? (raw.by_endpoint || {}) : {}

  const categories = history.map((h: any, i: number) => {
    if (h.timestamp) {
      const ts = typeof h.timestamp === 'number' ? h.timestamp : parseFloat(h.timestamp)
      if (!isNaN(ts)) {
        const d = new Date(ts * 1000)
        if (!isNaN(d.getTime())) return d.toLocaleTimeString('zh-CN', { hour12: false })
      }
    }
    return `${i + 1}s`
  })
  const p50Data = history.map((h: any) => h.p50 || 0)
  const p95Data = history.map((h: any) => h.p95 || 0)
  const p99Data = history.map((h: any) => h.p99 || 0)
  const rpsData = history.map((h: any) => h.rps || 0)

  const legendData = ['P50', 'P95', 'P99', 'RPS']
  const series: any[] = [
    { name: 'P50', type: 'line', data: p50Data, smooth: true },
    { name: 'P95', type: 'line', data: p95Data, smooth: true },
    { name: 'P99', type: 'line', data: p99Data, smooth: true },
    { name: 'RPS', type: 'line', data: rpsData, smooth: true, yAxisIndex: 1, lineStyle: { type: 'dashed' } },
  ]

  instance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: legendData, type: 'scroll' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 15 ? 30 : 0 } },
    yAxis: [
      { type: 'value', name: 'ms', position: 'left' },
      { type: 'value', name: 'RPS', position: 'right' },
    ],
    series,
  }, true)
}

function handleResize() {
  chartInstance?.resize()
  detailChartInstance?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  stopPolling()
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  detailChartInstance?.dispose()
})
</script>

<style scoped>
.perf-run-detail { padding: 0; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.page-header h2 { margin: 0; flex: 1; }
.header-actions { display: flex; gap: 8px; }
.chart-container { height: 300px; }
.chart-empty { height: 300px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
</style>

<style>
.selected-run-row {
  background-color: #e6f4ff !important;
}
.selected-run-row:hover > td {
  background-color: #bae0ff !important;
}
</style>
