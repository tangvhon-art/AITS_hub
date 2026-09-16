<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h2>质量看板</h2>
      <div>
        <a-select
          v-model:value="selectedVersionId"
          placeholder="全部版本"
          allow-clear
          style="width: 150px; margin-right: 8px"
          @change="loadAll"
        >
          <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
        </a-select>
        <a-select v-model:value="days" style="width: 120px; margin-right: 8px" @change="loadDashboard">
          <a-select-option :value="7">近7天</a-select-option>
          <a-select-option :value="14">近14天</a-select-option>
          <a-select-option :value="30">近30天</a-select-option>
        </a-select>
        <a-button @click="loadDashboard">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button type="primary" style="margin-left: 8px" @click="handleGenerateInsight" :loading="insightLoading">
          <RobotOutlined /> 生成洞察
        </a-button>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <a-row :gutter="16" class="metrics-row">
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="用例总数" :value="metrics.total_cases" />
          <div class="metric-sub">活跃 {{ metrics.active_cases }}</div>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="执行次数" :value="metrics.total_runs" />
          <div class="metric-sub">通过 {{ metrics.passed_runs }} / 失败 {{ metrics.failed_runs }}</div>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="通过率" :value="metrics.pass_rate" suffix="%" />
          <a-progress :percent="metrics.pass_rate" size="small" :show-info="false" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="缺陷总数" :value="metrics.total_defects" />
          <div class="metric-sub">未解决 {{ metrics.open_defects }}</div>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="缺陷密度" :value="metrics.defect_density" />
          <div class="metric-sub">缺陷/用例</div>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <a-statistic title="测试计划" :value="metrics.total_plans" />
          <div class="metric-sub">已完成 {{ metrics.completed_plans }}</div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 覆盖率指标卡片 -->
    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="5">
        <a-card class="metric-card">
          <a-statistic title="接口覆盖率" :value="coverageData.api_coverage_rate" suffix="%" />
          <a-progress :percent="coverageData.api_coverage_rate" size="small" :show-info="false" />
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card class="metric-card">
          <a-statistic title="场景覆盖率" :value="coverageData.scenario_coverage_rate" suffix="%" />
          <a-progress :percent="coverageData.scenario_coverage_rate" size="small" :show-info="false" />
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card class="metric-card">
          <a-statistic title="已覆盖接口" :value="coverageData.covered_apis" />
          <div class="metric-sub">总计 {{ coverageData.total_apis }}</div>
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card class="metric-card">
          <a-statistic title="未覆盖接口" :value="coverageData.uncovered_apis.length" value-style="color: #ff4d4f" />
          <div class="metric-sub">用例关联 {{ coverageData.cases_with_api }} / {{ coverageData.total_cases }}</div>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card class="metric-card">
          <div style="text-align: center; padding-top: 8px">
            <a-button type="primary" size="small" @click="handleRecalculate" :loading="coverageLoading">
              重新计算
            </a-button>
            <div class="metric-sub" style="margin-top: 8px">
              {{ coverageData.calculated_at ? '更新于 ' + coverageData.calculated_at.substring(5, 16) : '未计算' }}
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 图表区域 -->
    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="12">
        <a-card title="通过率趋势">
          <div ref="passRateChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="执行次数趋势">
          <div ref="executionChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="8">
        <a-card title="缺陷严重程度分布">
          <div ref="severityChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="缺陷根因分类">
          <div ref="categoryChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="模块通过率">
          <div ref="moduleChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 覆盖率趋势与未覆盖接口 -->
    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="14">
        <a-card title="覆盖率趋势">
          <div ref="coverageChartRef" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="10">
        <a-card title="未覆盖接口列表">
          <a-list :data-source="coverageData.uncovered_apis.slice(0, 10)" size="small" :pagination="{ pageSize: 5, size: 'small' }">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-tag :color="methodColor(item.method)">{{ item.method }}</a-tag>
                    <span style="font-size: 13px">{{ item.path }}</span>
                  </template>
                  <template #description>{{ item.name }}</template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="coverageData.uncovered_apis.length === 0" description="所有接口已覆盖" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 风险预警 -->
    <a-card title="风险预警" style="margin-top: 16px">
      <a-row :gutter="16" style="margin-bottom: 12px">
        <a-col :span="6">
          <a-statistic title="高危" :value="alerts.high" value-style="color: #ff4d4f" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="中危" :value="alerts.medium" value-style="color: #faad14" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="低危" :value="alerts.low" value-style="color: #52c41a" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="总计" :value="alerts.total" />
        </a-col>
      </a-row>
      <a-list :data-source="alerts.items" size="small">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-tag :color="getAlertColor(item.level)">{{ getAlertLevelText(item.level) }}</a-tag>
                {{ item.title }}
              </template>
              <template #description>{{ item.description }}</template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-if="alerts.items.length === 0" description="暂无风险预警" />
    </a-card>

    <!-- 洞察分析弹窗 -->
    <a-modal v-model:open="showInsightModal" title="AI 质量洞察分析" width="700px" :footer="null">
      <div v-if="insightData">
        <a-alert message="洞察分析结果" type="info" show-icon style="margin-bottom: 16px" />
        <a-list :data-source="insightData.insights" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <BulbOutlined style="color: #faad14; margin-right: 8px" />
              {{ item }}
            </a-list-item>
          </template>
        </a-list>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined, RobotOutlined, BulbOutlined
} from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import {
  getQualityDashboard, getRiskAlerts, generateInsight,
  type QualityDashboard, type RiskAlertResponse, type InsightResponse
} from '@/api/quality'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'
import { coverageApi, type CoverageData } from '@/api/coverage'

const route = useRoute()
const projectId = Number(route.params.id)

const days = ref(7)
const loading = ref(false)
const insightLoading = ref(false)
const showInsightModal = ref(false)
const insightData = ref<InsightResponse | null>(null)
const versions = ref<ProjectVersion[]>([])
const selectedVersionId = ref<number | undefined>(undefined)

const metrics = ref({
  total_cases: 0,
  active_cases: 0,
  total_runs: 0,
  passed_runs: 0,
  failed_runs: 0,
  pass_rate: 0,
  total_defects: 0,
  open_defects: 0,
  resolved_defects: 0,
  defect_density: 0,
  avg_duration: 0,
  total_plans: 0,
  completed_plans: 0
})

const alerts = ref<RiskAlertResponse>({ total: 0, high: 0, medium: 0, low: 0, items: [] })

const coverageData = ref<CoverageData>({
  total_apis: 0,
  covered_apis: 0,
  api_coverage_rate: 0,
  uncovered_apis: [],
  total_scenarios: 0,
  covered_scenarios: 0,
  scenario_coverage_rate: 0,
  total_cases: 0,
  cases_with_api: 0,
  calculated_at: null,
})
const coverageTrend = ref<any[]>([])
const coverageLoading = ref(false)

const passRateChartRef = ref<HTMLElement>()
const executionChartRef = ref<HTMLElement>()
const severityChartRef = ref<HTMLElement>()
const categoryChartRef = ref<HTMLElement>()
const moduleChartRef = ref<HTMLElement>()
const coverageChartRef = ref<HTMLElement>()

let passRateChart: echarts.ECharts | null = null
let executionChart: echarts.ECharts | null = null
let severityChart: echarts.ECharts | null = null
let categoryChart: echarts.ECharts | null = null
let moduleChart: echarts.ECharts | null = null
let coverageChart: echarts.ECharts | null = null

function getAlertColor(level?: string) {
  const map: Record<string, string> = { high: 'red', medium: 'orange', low: 'green' }
  return map[level || ''] || 'default'
}

function getAlertLevelText(level?: string) {
  const map: Record<string, string> = { high: '高危', medium: '中危', low: '低危' }
  return map[level || ''] || level
}

function methodColor(method?: string) {
  const map: Record<string, string> = {
    GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red', PATCH: 'purple'
  }
  return map[(method || '').toUpperCase()] || 'default'
}

function initCharts() {
  if (passRateChartRef.value) passRateChart = echarts.init(passRateChartRef.value)
  if (executionChartRef.value) executionChart = echarts.init(executionChartRef.value)
  if (severityChartRef.value) severityChart = echarts.init(severityChartRef.value)
  if (categoryChartRef.value) categoryChart = echarts.init(categoryChartRef.value)
  if (moduleChartRef.value) moduleChart = echarts.init(moduleChartRef.value)
  if (coverageChartRef.value) coverageChart = echarts.init(coverageChartRef.value)
}

function updateCharts(data: QualityDashboard) {
  // 通过率趋势
  if (passRateChart) {
    passRateChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: data.trend.pass_rate_trend.map(d => d.date) },
      yAxis: { type: 'value', max: 100, name: '%' },
      series: [{
        data: data.trend.pass_rate_trend.map(d => d.value),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#52c41a' },
        lineStyle: { color: '#52c41a' }
      }]
    })
  }

  // 执行次数趋势
  if (executionChart) {
    executionChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['执行次数', '缺陷数'], top: 0 },
      grid: { left: 40, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: data.trend.execution_trend.map(d => d.date) },
      yAxis: { type: 'value' },
      series: [
        {
          name: '执行次数',
          data: data.trend.execution_trend.map(d => d.value),
          type: 'bar',
          itemStyle: { color: '#1677ff' }
        },
        {
          name: '缺陷数',
          data: data.trend.defect_trend.map(d => d.value),
          type: 'line',
          smooth: true,
          itemStyle: { color: '#ff4d4f' }
        }
      ]
    })
  }

  // 严重程度分布
  if (severityChart) {
    severityChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: data.severity_distribution.map(d => ({ name: d.category, value: d.count })),
        label: { formatter: '{b}: {c}' }
      }]
    })
  }

  // 根因分类
  if (categoryChart) {
    categoryChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: data.category_distribution.map(d => ({ name: d.category, value: d.count })),
        label: { formatter: '{b}: {c}' }
      }]
    })
  }

  // 模块通过率
  if (moduleChart) {
    moduleChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 80, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'value', max: 100, name: '%' },
      yAxis: { type: 'category', data: data.module_pass_rate.map(m => m.module) },
      series: [{
        type: 'bar',
        data: data.module_pass_rate.map(m => ({
          value: m.pass_rate,
          itemStyle: { color: m.pass_rate >= 80 ? '#52c41a' : m.pass_rate >= 60 ? '#faad14' : '#ff4d4f' }
        })),
        label: { show: true, position: 'right', formatter: '{c}%' }
      }]
    })
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    const data = await getQualityDashboard(projectId, days.value, selectedVersionId.value)
    metrics.value = data.metrics
    updateCharts(data)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载看板失败')
  } finally {
    loading.value = false
  }
}

function updateCoverageChart() {
  if (!coverageChart) return
  coverageChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['接口覆盖率', '场景覆盖率'], top: 0 },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: coverageTrend.value.map(d => d.date) },
    yAxis: { type: 'value', max: 100, name: '%' },
    series: [
      {
        name: '接口覆盖率',
        data: coverageTrend.value.map(d => d.api_coverage_rate),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#1677ff' },
        lineStyle: { color: '#1677ff' },
      },
      {
        name: '场景覆盖率',
        data: coverageTrend.value.map(d => d.scenario_coverage_rate),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#722ed1' },
        lineStyle: { color: '#722ed1' },
      },
    ],
  })
}

async function loadCoverage() {
  try {
    const [data, trend] = await Promise.all([
      coverageApi.get(projectId, selectedVersionId.value),
      coverageApi.getTrend(projectId, 30),
    ])
    coverageData.value = data
    coverageTrend.value = trend
    updateCoverageChart()
  } catch (e: any) {
    console.error('加载覆盖率失败', e)
  }
}

async function handleRecalculate() {
  coverageLoading.value = true
  try {
    await coverageApi.recalculate(projectId, selectedVersionId.value)
    message.success('覆盖率重新计算完成')
    await loadCoverage()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '重新计算失败')
  } finally {
    coverageLoading.value = false
  }
}

async function loadAlerts() {
  try {
    alerts.value = await getRiskAlerts(projectId, selectedVersionId.value)
  } catch (e: any) {
    console.error('加载预警失败', e)
  }
}

async function handleGenerateInsight() {
  insightLoading.value = true
  try {
    insightData.value = await generateInsight(projectId, selectedVersionId.value)
    showInsightModal.value = true
  } catch (e: any) {
    message.error(e.response?.data?.detail || '生成洞察失败')
  } finally {
    insightLoading.value = false
  }
}

function handleResize() {
  passRateChart?.resize()
  executionChart?.resize()
  severityChart?.resize()
  categoryChart?.resize()
  moduleChart?.resize()
  coverageChart?.resize()
}

async function loadAll() {
  loadDashboard()
  loadAlerts()
  loadCoverage()
}

onMounted(async () => {
  await nextTick()
  initCharts()
  loadDashboard()
  loadAlerts()
  loadCoverage()
  if (projectId) {
    getVersions(projectId, { page_size: 200 }).then(data => { versions.value = data.items }).catch(() => {})
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  passRateChart?.dispose()
  executionChart?.dispose()
  severityChart?.dispose()
  categoryChart?.dispose()
  moduleChart?.dispose()
  coverageChart?.dispose()
})
</script>

<style scoped>
.dashboard-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.metrics-row .metric-card { text-align: center; }
.metric-sub { font-size: 12px; color: #999; margin-top: 4px; }
.chart-container { height: 280px; }
</style>
