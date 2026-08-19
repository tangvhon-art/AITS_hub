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
      <a-col :span="4"><a-card><a-statistic title="QPS" :value="run.requests_per_second || 0" :precision="1" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="平均响应" :value="run.avg_response_time || 0" :precision="1" suffix="ms" /></a-card></a-col>
      <a-col :span="4"><a-card><a-statistic title="P95响应" :value="run.p95_response_time || 0" :precision="1" suffix="ms" :value-style="{ color: (run.p95_response_time || 0) > 1000 ? '#cf1322' : '#3f8600' }" /></a-card></a-col>
    </a-row>

    <!-- JMeter 风格聚合报告 -->
    <a-card v-if="endpointStats.length > 0" title="聚合报告（JMeter 风格）" style="margin-bottom: 16px">
      <a-table :columns="aggregateColumns" :data-source="endpointStats" :pagination="false" row-key="label" size="small" :scroll="{ x: 1400 }" :row-class-name="(record: any) => record.is_total ? 'total-row' : ''">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'error_pct'">
            <span :style="{ color: record.error_pct > 0 ? '#cf1322' : '#3f8600' }">{{ record.error_pct }}%</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 性能指标汇总（整行） -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="24">
        <a-card title="性能指标汇总">
          <a-descriptions :column="4" bordered size="small">
            <a-descriptions-item label="状态"><a-tag :color="statusColor(run.status)">{{ statusText(run.status) }}</a-tag></a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ run.started_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="结束时间">{{ run.finished_at || '-' }}</a-descriptions-item>
            <a-descriptions-item label="总请求数">{{ run.total_requests || 0 }}</a-descriptions-item>
            <a-descriptions-item label="最小响应">{{ run.min_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="最大响应">{{ run.max_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P50响应">{{ run.p50_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P95响应">{{ run.p95_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="P99响应">{{ run.p99_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="平均响应">{{ run.avg_response_time?.toFixed(1) || 0 }} ms</a-descriptions-item>
            <a-descriptions-item label="QPS">{{ run.requests_per_second?.toFixed(1) || 0 }}</a-descriptions-item>
            <a-descriptions-item label="失败率">{{ run.failure_rate || 0 }}%</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
    </a-row>

    <!-- Locust 趋势图：2x2 布局 -->
    <a-row :gutter="16" v-if="hasTrendData">
      <a-col :span="12">
        <a-card title="运行趋势（虚拟用户数 / QPS）">
          <div ref="responseChartRef" class="chart-container"></div>
          <a-empty v-if="!hasTrendData" :description="trendEmptyText" class="chart-empty" />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="Total Requests per Second（QPS 趋势）">
          <div ref="rpsChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="12" style="margin-top: 16px">
        <a-card title="Response Times (ms) 响应时间趋势">
          <div ref="respTimeChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="12" style="margin-top: 16px">
        <a-card title="Number of Users 虚拟用户数趋势">
          <div ref="usersChartRef" class="chart-container"></div>
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
          <a-col :span="8"><a-card size="small"><a-statistic title="QPS" :value="detailRun.requests_per_second || 0" :precision="1" /></a-card></a-col>
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
// Locust 标准 4 张趋势图
const rpsChartRef = ref<HTMLElement>()
const respTimeChartRef = ref<HTMLElement>()
const usersChartRef = ref<HTMLElement>()
const failuresChartRef = ref<HTMLElement>()
let rpsChartInstance: echarts.ECharts | null = null
let respTimeChartInstance: echarts.ECharts | null = null
let usersChartInstance: echarts.ECharts | null = null
let failuresChartInstance: echarts.ECharts | null = null
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
  { title: 'QPS', dataIndex: 'requests_per_second', key: 'requests_per_second', width: 80 },
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
  { title: 'Name', dataIndex: 'label', key: 'label', width: 200, fixed: 'left' },
  { title: '# requests', dataIndex: 'samples', key: 'samples', width: 100 },
  { title: '# failures', dataIndex: 'failures', key: 'failures', width: 100 },
  { title: 'Median', dataIndex: 'median', key: 'median', width: 90 },
  { title: '90%', dataIndex: 'p90', key: 'p90', width: 80 },
  { title: '95%', dataIndex: 'p95', key: 'p95', width: 80 },
  { title: '99%', dataIndex: 'p99', key: 'p99', width: 80 },
  { title: 'Average', dataIndex: 'average', key: 'average', width: 90, sorter: (a: any, b: any) => a.average - b.average },
  { title: 'Min', dataIndex: 'min', key: 'min', width: 80 },
  { title: 'Max', dataIndex: 'max', key: 'max', width: 80 },
  { title: 'Average size', dataIndex: 'avg_size_bytes', key: 'avg_size_bytes', width: 110 },
  { title: 'QPS', dataIndex: 'throughput', key: 'throughput', width: 90 },
  { title: '失败率', key: 'error_pct', width: 90 },
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
    // 渲染 Locust 标准 4 张趋势图
    renderLocustCharts()
  })
}

/** 从 stats_history 提取时间轴和数据序列 */
function extractTrendData(data: Partial<PerformanceTestRun>) {
  const raw = data.stats_history
  const history: any[] = Array.isArray(raw) ? raw : (raw?.aggregate || [])
  const byEndpoint: Record<string, any[]> = !Array.isArray(raw) && raw?.by_endpoint ? raw.by_endpoint : {}

  // 时间戳 -> 各接口 avg 列表（兜底用）
  const endpointAvgByTs: Record<string, number[]> = {}
  for (const epRecords of Object.values(byEndpoint)) {
    for (const rec of epRecords) {
      const ts = String(rec.timestamp || '')
      const avg = rec.avg ?? rec.average ?? rec.avg_response_time ?? 0
      if (avg > 0) {
        if (!endpointAvgByTs[ts]) endpointAvgByTs[ts] = []
        endpointAvgByTs[ts].push(avg)
      }
    }
  }

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

  const getAvg = (h: any) => {
    const rawAvg = h.avg ?? h.average ?? h.avg_response_time ?? 0
    if (rawAvg > 0) return rawAvg
    const ts = String(h.timestamp || '')
    const epAvgs = endpointAvgByTs[ts]
    return epAvgs && epAvgs.length > 0 ? Math.round((epAvgs.reduce((a, b) => a + b, 0) / epAvgs.length) * 100) / 100 : 0
  }

  return {
    categories,
    rps: history.map((h: any) => h.rps || 0),
    failuresPerS: history.map((h: any) => h.failures_per_s ?? h.failures ?? 0),
    p50: history.map((h: any) => h.p50 ?? h.median ?? 0),
    p95: history.map((h: any) => h.p95 || 0),
    p99: history.map((h: any) => h.p99 || 0),
    avg: history.map((h: any) => getAvg(h)),
    users: history.map((h: any) => h.users || 0),
  }
}

/** 渲染 Locust 标准 4 张趋势图 */
function renderLocustCharts() {
  const trend = extractTrendData(run.value)
  const commonGrid = { left: '3%', right: '4%', bottom: '3%', containLabel: true }
  const commonTooltip = { trigger: 'axis' }

  // 1. RPS 趋势（RPS + Failures/s）
  if (rpsChartRef.value) {
    if (!rpsChartInstance) rpsChartInstance = echarts.init(rpsChartRef.value)
    rpsChartInstance.setOption({
      tooltip: commonTooltip,
      legend: { data: ['QPS', 'Failures/s'], type: 'scroll' },
      grid: commonGrid,
      xAxis: { type: 'category', data: trend.categories, axisLabel: { rotate: trend.categories.length > 15 ? 30 : 0 } },
      yAxis: { type: 'value', name: '次/秒' },
      series: [
        { name: 'QPS', type: 'line', data: trend.rps, smooth: true, areaStyle: { opacity: 0.1 }, itemStyle: { color: '#1677ff' } },
        { name: 'Failures/s', type: 'line', data: trend.failuresPerS, smooth: true, itemStyle: { color: '#cf1322' }, lineStyle: { type: 'dashed' } },
      ],
    })
  }

  // 2. 响应时间趋势（P50 + P95 + P99）
  if (respTimeChartRef.value) {
    if (!respTimeChartInstance) respTimeChartInstance = echarts.init(respTimeChartRef.value)
    respTimeChartInstance.setOption({
      tooltip: commonTooltip,
      legend: { data: ['Median(P50)', 'P95', 'P99'], type: 'scroll' },
      grid: commonGrid,
      xAxis: { type: 'category', data: trend.categories, axisLabel: { rotate: trend.categories.length > 15 ? 30 : 0 } },
      yAxis: { type: 'value', name: 'ms' },
      series: [
        { name: 'Median(P50)', type: 'line', data: trend.p50, smooth: true, itemStyle: { color: '#52c41a' } },
        { name: 'P95', type: 'line', data: trend.p95, smooth: true, itemStyle: { color: '#faad14' } },
        { name: 'P99', type: 'line', data: trend.p99, smooth: true, itemStyle: { color: '#f5222d' } },
      ],
    })
  }

  // 3. 虚拟用户数趋势
  if (usersChartRef.value) {
    if (!usersChartInstance) usersChartInstance = echarts.init(usersChartRef.value)
    usersChartInstance.setOption({
      tooltip: commonTooltip,
      grid: commonGrid,
      xAxis: { type: 'category', data: trend.categories, axisLabel: { rotate: trend.categories.length > 15 ? 30 : 0 } },
      yAxis: { type: 'value', name: '用户数' },
      series: [
        { name: '虚拟用户数', type: 'line', data: trend.users, smooth: true, areaStyle: { opacity: 0.2 }, itemStyle: { color: '#722ed1' }, step: 'end' },
      ],
    })
  }

  // 4. 每秒失败趋势
  if (failuresChartRef.value) {
    if (!failuresChartInstance) failuresChartInstance = echarts.init(failuresChartRef.value)
    failuresChartInstance.setOption({
      tooltip: commonTooltip,
      grid: commonGrid,
      xAxis: { type: 'category', data: trend.categories, axisLabel: { rotate: trend.categories.length > 15 ? 30 : 0 } },
      yAxis: { type: 'value', name: '失败数/秒' },
      series: [
        { name: 'Failures/s', type: 'line', data: trend.failuresPerS, smooth: true, areaStyle: { opacity: 0.15 }, itemStyle: { color: '#cf1322' } },
      ],
    })
  }
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
  const byEndpoint: Record<string, any[]> = !Array.isArray(raw) && raw?.by_endpoint ? raw.by_endpoint : {}

  // 构建时间戳 -> 各接口 avg 列表的映射，用于 aggregate avg 为0时兜底计算
  const endpointAvgByTs: Record<string, number[]> = {}
  for (const epRecords of Object.values(byEndpoint)) {
    for (const rec of epRecords) {
      const ts = String(rec.timestamp || '')
      const avg = rec.avg ?? rec.average ?? rec.avg_response_time ?? 0
      if (avg > 0) {
        if (!endpointAvgByTs[ts]) endpointAvgByTs[ts] = []
        endpointAvgByTs[ts].push(avg)
      }
    }
  }

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
  const avgData = history.map((h: any) => {
    const rawAvg = h.avg ?? h.average ?? h.avg_response_time ?? 0
    if (rawAvg > 0) return rawAvg
    // 兜底1：用同时间戳各接口 avg 的平均值
    const ts = String(h.timestamp || '')
    const epAvgs = endpointAvgByTs[ts]
    if (epAvgs && epAvgs.length > 0) {
      const calc = Math.round((epAvgs.reduce((a, b) => a + b, 0) / epAvgs.length) * 100) / 100
      if (calc > 0) return calc
    }
    // 兜底2：Locust stats_history 的 Average 列常为0，用 P50/中位数替代
    const p50 = h.p50 ?? h.median ?? 0
    if (p50 > 0) return Math.round(p50 * 100) / 100
    return 0
  })
  const usersData = history.map((h: any) => h.users || 0)
  const rpsData = history.map((h: any) => {
    const rawRps = h.rps || 0
    if (rawRps > 0) return rawRps
    // 兜底：用同时间戳各接口 rps 总和
    const ts = String(h.timestamp || '')
    let totalRps = 0
    for (const epRecords of Object.values(byEndpoint)) {
      for (const rec of epRecords) {
        if (String(rec.timestamp || '') === ts) {
          totalRps += rec.rps || 0
        }
      }
    }
    return totalRps > 0 ? Math.round(totalRps * 100) / 100 : 0
  })

  const legendData = ['虚拟用户数', 'QPS']
  const series: any[] = [
    { name: '虚拟用户数', type: 'line', data: usersData, smooth: true, lineStyle: { type: 'dashed' } },
    { name: 'QPS', type: 'line', data: rpsData, smooth: true, areaStyle: { opacity: 0.1 } },
  ]

  instance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: legendData, type: 'scroll' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 15 ? 30 : 0 } },
    yAxis: { type: 'value', name: '数量' },
    series,
  }, true)
}

function handleResize() {
  chartInstance?.resize()
  detailChartInstance?.resize()
  rpsChartInstance?.resize()
  respTimeChartInstance?.resize()
  usersChartInstance?.resize()
  failuresChartInstance?.resize()
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
  rpsChartInstance?.dispose()
  respTimeChartInstance?.dispose()
  usersChartInstance?.dispose()
  failuresChartInstance?.dispose()
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
.total-row > td {
  background-color: #fafafa !important;
  font-weight: 600;
}
.total-row:hover > td {
  background-color: #f0f0f0 !important;
}
</style>
