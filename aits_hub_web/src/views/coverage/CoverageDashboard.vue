<template>
  <div class="coverage-page">
    <PageHeader title="覆盖率分析">
      <template #extra>
        <a-select
          v-model:value="selectedVersionId"
          placeholder="全部版本"
          allow-clear
          style="width: 150px"
          @change="handleVersionChange"
        >
          <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
        </a-select>
        <a-button @click="loadAll">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button type="primary" @click="handleRecalculate" :loading="recalculating">
          <CalculatorOutlined /> 重新计算
        </a-button>
      </template>
    </PageHeader>

    <!-- 总览卡片 -->
    <a-row :gutter="16" class="metrics-row">
      <a-col :span="6">
        <a-card class="metric-card">
          <a-statistic title="接口总数" :value="coverage.total_apis" />
          <div class="metric-sub">已覆盖 {{ coverage.covered_apis }} / 未覆盖 {{ coverage.total_apis - coverage.covered_apis }}</div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="metric-card">
          <a-statistic
            title="接口覆盖率"
            :value="coverage.api_coverage_rate"
            suffix="%"
            :value-style="{ color: rateColor(coverage.api_coverage_rate) }"
          />
          <a-progress
            :percent="coverage.api_coverage_rate"
            size="small"
            :show-info="false"
            :stroke-color="rateColor(coverage.api_coverage_rate)"
          />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="metric-card">
          <a-statistic title="场景覆盖率" :value="coverage.scenario_coverage_rate" suffix="%" />
          <div class="metric-sub">已覆盖 {{ coverage.covered_scenarios }} / 总计 {{ coverage.total_scenarios }}</div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="metric-card">
          <a-statistic title="用例关联率" :value="caseLinkRate" suffix="%" />
          <div class="metric-sub">关联接口 {{ coverage.cases_with_api }} / 总用例 {{ coverage.total_cases }}</div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 覆盖率趋势图 -->
    <a-card title="覆盖率趋势" style="margin-top: 16px">
      <template #extra>
        <a-radio-group v-model:value="trendDays" size="small" @change="loadTrend">
          <a-radio-button :value="7">近7天</a-radio-button>
          <a-radio-button :value="30">近30天</a-radio-button>
          <a-radio-button :value="90">近90天</a-radio-button>
        </a-radio-group>
      </template>
      <div ref="trendChartRef" class="chart-container"></div>
      <a-empty v-if="trendData.length === 0" description="暂无趋势数据，请先计算覆盖率" />
    </a-card>

    <!-- 未覆盖接口列表 -->
    <a-card title="未覆盖接口列表" style="margin-top: 16px">
      <a-table
        :columns="uncoveredColumns"
        :data-source="uncoveredList"
        :pagination="{ pageSize: 10, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
        :loading="loading"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
          </template>
          <template v-else-if="column.key === 'path'">
            <span class="api-path">{{ record.path }}</span>
          </template>
          <template v-else-if="column.key === 'name'">
            {{ record.name || '-' }}
          </template>
        </template>
      </a-table>
      <a-empty v-if="uncoveredList.length === 0 && !loading" description="所有接口已覆盖 🎉" />
    </a-card>

    <!-- 覆盖率配置 -->
    <a-card title="覆盖率配置" style="margin-top: 16px">
      <a-form layout="vertical" style="max-width: 600px">
        <a-form-item label="排除路径（支持通配符，每行一个）">
          <a-textarea
            v-model:value="configForm.excluded_paths_text"
            placeholder="例如：&#10;/api/health&#10;/api/internal/*&#10;*/docs"
            :rows="4"
          />
          <div class="form-hint">匹配的接口路径将不参与覆盖率计算，支持 fnmatch 通配符（*、?）</div>
        </a-form-item>
        <a-form-item label="排除 HTTP 方法">
          <a-select
            v-model:value="configForm.excluded_methods"
            mode="multiple"
            placeholder="选择不参与统计的 HTTP 方法"
            style="width: 100%"
          >
            <a-select-option value="GET">GET</a-select-option>
            <a-select-option value="POST">POST</a-select-option>
            <a-select-option value="PUT">PUT</a-select-option>
            <a-select-option value="DELETE">DELETE</a-select-option>
            <a-select-option value="PATCH">PATCH</a-select-option>
            <a-select-option value="HEAD">HEAD</a-select-option>
            <a-select-option value="OPTIONS">OPTIONS</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键场景 ID（用于场景覆盖率计算）">
          <a-input
            v-model:value="configForm.critical_scenario_ids_text"
            placeholder="多个 ID 用英文逗号分隔，例如：1,2,3"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="saveConfig" :loading="savingConfig">保存配置</a-button>
          <a-button style="margin-left: 8px" @click="handleRecalculate" :loading="recalculating">保存并重新计算</a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined, CalculatorOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import { coverageApi, type CoverageData, type CoverageConfig } from '@/api/coverage'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const recalculating = ref(false)
const savingConfig = ref(false)
const versions = ref<ProjectVersion[]>([])
const selectedVersionId = ref<number | undefined>(undefined)
const trendDays = ref(30)

const coverage = ref<CoverageData>({
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

const trendData = ref<any[]>([])
const uncoveredList = ref<any[]>([])

const configForm = ref({
  excluded_paths_text: '',
  excluded_methods: [] as string[],
  critical_scenario_ids_text: '',
  version_id: undefined as number | undefined,
})

const caseLinkRate = computed(() => {
  if (!coverage.value.total_cases) return 0
  return Math.round((coverage.value.cases_with_api / coverage.value.total_cases) * 10000) / 100
})

const uncoveredColumns = [
  { title: '方法', dataIndex: 'method', key: 'method', width: 100 },
  { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
  { title: '接口名称', dataIndex: 'name', key: 'name', ellipsis: true },
]

const trendChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

function rateColor(rate: number): string {
  if (rate >= 80) return '#52c41a'
  if (rate >= 60) return '#faad14'
  return '#ff4d4f'
}

function methodColor(method?: string): string {
  const map: Record<string, string> = {
    GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red', PATCH: 'purple',
  }
  return map[(method || '').toUpperCase()] || 'default'
}

function initChart() {
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
  }
}

function updateTrendChart() {
  if (!trendChart) return
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['接口覆盖率', '场景覆盖率'], top: 0 },
    grid: { left: 50, right: 30, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: trendData.value.map(d => d.date),
      axisLabel: { rotate: trendData.value.length > 10 ? 30 : 0 },
    },
    yAxis: { type: 'value', max: 100, name: '%' },
    series: [
      {
        name: '接口覆盖率',
        data: trendData.value.map(d => d.api_coverage_rate),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.2 },
        itemStyle: { color: '#1677ff' },
        lineStyle: { color: '#1677ff' },
      },
      {
        name: '场景覆盖率',
        data: trendData.value.map(d => d.scenario_coverage_rate),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.2 },
        itemStyle: { color: '#52c41a' },
        lineStyle: { color: '#52c41a' },
      },
    ],
  })
}

async function loadCoverage() {
  loading.value = true
  try {
    const data = await coverageApi.get(projectId, selectedVersionId.value)
    coverage.value = data
    uncoveredList.value = data.uncovered_apis || []
  } catch (e: any) {
    if (e.response?.status !== 404) {
      message.error(e.response?.data?.detail || '加载覆盖率数据失败')
    }
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  try {
    const data = await coverageApi.getTrend(projectId, trendDays.value)
    trendData.value = data || []
    updateTrendChart()
  } catch (e: any) {
    console.error('加载趋势失败', e)
  }
}

async function loadConfig() {
  try {
    const config = await coverageApi.getConfig(projectId)
    configForm.value.excluded_paths_text = (config.excluded_paths || []).join('\n')
    configForm.value.excluded_methods = config.excluded_methods || []
    configForm.value.critical_scenario_ids_text = (config.critical_scenario_ids || []).join(',')
    configForm.value.version_id = config.version_id ?? undefined
  } catch (e: any) {
    console.error('加载配置失败', e)
  }
}

async function saveConfig(andRecalculate = false) {
  savingConfig.value = true
  try {
    const excludedPaths = configForm.value.excluded_paths_text
      .split('\n')
      .map(s => s.trim())
      .filter(Boolean)
    const criticalIds = configForm.value.critical_scenario_ids_text
      .split(',')
      .map(s => parseInt(s.trim(), 10))
      .filter(n => !isNaN(n))

    await coverageApi.updateConfig(projectId, {
      excluded_paths: excludedPaths,
      excluded_methods: configForm.value.excluded_methods,
      critical_scenario_ids: criticalIds,
    })
    message.success('配置保存成功')
    if (andRecalculate) {
      await doRecalculate()
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

async function doRecalculate() {
  recalculating.value = true
  try {
    const data = await coverageApi.recalculate(projectId, selectedVersionId.value)
    coverage.value = { ...coverage.value, ...data }
    uncoveredList.value = data.uncovered_apis || []
    message.success('覆盖率重新计算完成')
    await loadTrend()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '重新计算失败')
  } finally {
    recalculating.value = false
  }
}

async function handleRecalculate() {
  await doRecalculate()
}

function handleVersionChange() {
  loadCoverage()
}

function handleResize() {
  trendChart?.resize()
}

async function loadAll() {
  await Promise.all([loadCoverage(), loadTrend(), loadConfig()])
}

onMounted(async () => {
  await nextTick()
  initChart()
  loadAll()
  try {
    const data = await getVersions(projectId, { page_size: 200 })
    versions.value = data.items
  } catch {
    // ignore
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
})
</script>

<style scoped>
.coverage-page {
  padding: 20px;
}

.metrics-row .metric-card {
  text-align: center;
}

.metric-sub {
  font-size: 12px;
  color: #999;
  margin-top: 6px;
}

.chart-container {
  height: 320px;
}

.api-path {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  color: #1677ff;
}

.form-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
