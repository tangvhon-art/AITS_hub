<template>
  <div class="test-plan-report">
    <a-page-header :title="`测试报告 - ${execution?.plan_name || ''}`" @back="goBack">
      <template #extra>
        <a-button @click="goBack">返回列表</a-button>
        <a-button @click="reRun" v-if="execution">重新执行</a-button>
      </template>
    </a-page-header>

    <div v-if="execution" class="report-content">
      <!-- 基本信息 -->
      <a-card size="small" style="margin-bottom: 16px">
        <a-descriptions :column="4" bordered size="small">
          <a-descriptions-item label="计划名称">{{ execution.plan_name }}</a-descriptions-item>
          <a-descriptions-item label="执行环境">{{ execution.environment_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="getStatusColor(execution.status)">{{ getStatusText(execution.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="通过率">
            <span :style="{ color: execution.pass_rate >= 80 ? '#52c41a' : execution.pass_rate >= 60 ? '#faad14' : '#ff4d4f', fontWeight: 'bold' }">
              {{ execution.pass_rate }}%
            </span>
          </a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ formatDateTime(execution.started_at) }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ formatDateTime(execution.finished_at) }}</a-descriptions-item>
          <a-descriptions-item label="总耗时">{{ totalDuration }}</a-descriptions-item>
          <a-descriptions-item label="执行ID">#{{ execution.id }}</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <a-tabs v-model:activeKey="activeTab">
        <!-- 概览 Tab -->
        <a-tab-pane key="overview" tab="概览">
          <a-row :gutter="16" style="margin-bottom: 16px">
            <a-col :span="6">
              <a-card size="small">
                <a-statistic title="总节点数" :value="execution.total_items" />
              </a-card>
            </a-col>
            <a-col :span="6">
              <a-card size="small">
                <a-statistic title="通过数" :value="execution.passed_count" :value-style="{ color: '#52c41a' }" />
              </a-card>
            </a-col>
            <a-col :span="6">
              <a-card size="small">
                <a-statistic title="失败数" :value="execution.failed_count" :value-style="{ color: '#ff4d4f' }" />
              </a-card>
            </a-col>
            <a-col :span="6">
              <a-card size="small">
                <a-statistic title="跳过数" :value="execution.skipped_count" :value-style="{ color: '#faad14' }" />
              </a-card>
            </a-col>
          </a-row>

          <a-row :gutter="16">
            <a-col :span="12">
              <a-card size="small" title="通过率分布">
                <div class="chart-container">
                  <div class="pie-chart">
                    <svg viewBox="0 0 100 100" width="180" height="180">
                      <circle cx="50" cy="50" r="40" fill="none" stroke="#f0f0f0" stroke-width="12" />
                      <circle
                        cx="50" cy="50" r="40" fill="none"
                        :stroke="execution.pass_rate >= 80 ? '#52c41a' : execution.pass_rate >= 60 ? '#faad14' : '#ff4d4f'"
                        stroke-width="12"
                        :stroke-dasharray="`${execution.pass_rate * 2.51} 251`"
                        stroke-linecap="round"
                        transform="rotate(-90 50 50)"
                      />
                      <text x="50" y="48" text-anchor="middle" font-size="18" font-weight="bold" fill="#333">
                        {{ execution.pass_rate }}%
                      </text>
                      <text x="50" y="62" text-anchor="middle" font-size="10" fill="#999">通过率</text>
                    </svg>
                  </div>
                  <div class="legend">
                    <div class="legend-item">
                      <span class="legend-dot" style="background: #52c41a"></span>
                      通过: {{ execution.passed_count }}
                    </div>
                    <div class="legend-item">
                      <span class="legend-dot" style="background: #ff4d4f"></span>
                      失败: {{ execution.failed_count }}
                    </div>
                    <div class="legend-item">
                      <span class="legend-dot" style="background: #faad14"></span>
                      跳过: {{ execution.skipped_count }}
                    </div>
                  </div>
                </div>
              </a-card>
            </a-col>
            <a-col :span="12">
              <a-card size="small" title="失败节点 Top">
                <div v-if="failedResults.length > 0">
                  <div
                    v-for="(r, idx) in failedResults.slice(0, 5)"
                    :key="r.id"
                    class="failed-item"
                  >
                    <span class="failed-rank">{{ idx + 1 }}</span>
                    <span class="failed-name">{{ r.item_name }}</span>
                    <a-tag :color="getItemTypeColor(r.item_type)" size="small">
                      {{ getItemTypeLabel(r.item_type) }}
                    </a-tag>
                  </div>
                </div>
                <a-empty v-else description="无失败节点" />
              </a-card>
            </a-col>
          </a-row>
        </a-tab-pane>

        <!-- 详情 Tab -->
        <a-tab-pane key="details" tab="执行详情">
          <a-card size="small">
            <a-collapse>
              <a-collapse-panel
                v-for="result in results"
                :key="result.id"
              >
                <template #header>
                  <div class="collapse-header">
                    <span class="result-index">{{ result.sort_order + 1 }}</span>
                    <a-tag :color="getResultStatusColor(result.status)" size="small">
                      {{ getResultStatusText(result.status) }}
                    </a-tag>
                    <span class="result-name">{{ result.item_name }}</span>
                    <a-tag :color="getItemTypeColor(result.item_type)" size="small">
                      {{ getItemTypeLabel(result.item_type) }}
                    </a-tag>
                    <span class="result-duration">{{ result.duration_ms }}ms</span>
                    <span v-if="result.retry_count > 0" class="result-retry">重试{{ result.retry_count }}次</span>
                  </div>
                </template>

                <div class="result-detail">
                  <a-descriptions :column="2" bordered size="small" style="margin-bottom: 12px">
                    <a-descriptions-item label="节点类型">
                      {{ getItemTypeDetailLabel(result.item_type) }}
                    </a-descriptions-item>
                    <a-descriptions-item label="关联ID">{{ result.ref_id }}</a-descriptions-item>
                    <a-descriptions-item label="开始时间">{{ formatDateTime(result.started_at) }}</a-descriptions-item>
                    <a-descriptions-item label="结束时间">{{ formatDateTime(result.finished_at) }}</a-descriptions-item>
                  </a-descriptions>

                  <a-tabs :active-key="getDetailTab(result.id)" @change="(k: string) => setDetailTab(result.id, k)">
                    <a-tab-pane key="request" tab="请求信息">
                      <pre class="code-block">{{ formatJson(result.request_data) }}</pre>
                    </a-tab-pane>
                    <a-tab-pane key="response" tab="响应信息">
                      <pre class="code-block">{{ formatJson(result.response_data) }}</pre>
                    </a-tab-pane>
                    <a-tab-pane key="assertions" tab="断言结果">
                      <div v-if="result.assertions && result.assertions.length > 0">
                        <div
                          v-for="(a, idx) in result.assertions"
                          :key="idx"
                          class="assertion-item"
                        >
                          <a-tag :color="a.passed ? 'green' : 'red'">
                            {{ a.passed ? '通过' : '失败' }}
                          </a-tag>
                          <span class="assertion-text" v-if="hasAssertionText(a)">
                            {{ assertTypeLabel(a.assert_type) }}: {{ a.assert_target }} {{ a.operator }} {{ stringify(a.expected_value) }}
                          </span>
                          <span class="assertion-text" v-else>
                            {{ a.message || '断言详情缺失' }}
                          </span>
                          <span v-if="hasActualValue(a)" class="assertion-actual">
                            实际: {{ stringify(a.actual_value) }}
                          </span>
                          <span v-if="a.step_name" class="assertion-step">
                            <a-tag size="small" color="blue">步骤: {{ a.step_name }}</a-tag>
                          </span>
                        </div>
                      </div>
                      <a-empty v-else description="无断言配置" />
                    </a-tab-pane>
                    <a-tab-pane key="extracted" tab="提取变量" v-if="Object.keys(result.extracted_vars || {}).length > 0">
                      <pre class="code-block">{{ formatJson(result.extracted_vars) }}</pre>
                    </a-tab-pane>
                    <a-tab-pane key="error" tab="错误信息" v-if="result.error_message">
                      <a-alert type="error" :message="result.error_message" />
                    </a-tab-pane>
                  </a-tabs>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </a-card>
        </a-tab-pane>

        <!-- 日志 Tab -->
        <a-tab-pane key="logs" tab="执行日志">
          <a-card size="small">
            <div class="log-container">
              <div v-for="(log, idx) in logs" :key="idx" class="log-line">
                <span class="log-time">{{ log.time }}</span>
                <a-tag :color="log.level === 'ERROR' ? 'red' : log.level === 'WARN' ? 'orange' : 'blue'" size="small">
                  {{ log.level }}
                </a-tag>
                <span class="log-message">{{ log.message }}</span>
              </div>
              <div v-if="logs.length === 0" class="log-empty">
                暂无日志信息
              </div>
            </div>
          </a-card>
        </a-tab-pane>

        <!-- 导出 Tab -->
        <a-tab-pane key="export" tab="报告导出">
          <a-card size="small">
            <a-row :gutter="24">
              <a-col :span="8">
                <a-card hoverable class="export-card" @click="exportHtml">
                  <template #cover>
                    <div class="export-icon html-icon">
                      <FileTextOutlined />
                    </div>
                  </template>
                  <a-card-meta title="HTML 报告" description="可在浏览器中直接打开查看，包含完整的执行详情和统计信息" />
                </a-card>
              </a-col>
              <a-col :span="8">
                <a-card hoverable class="export-card" @click="exportJunit">
                  <template #cover>
                    <div class="export-icon xml-icon">
                      <CodeOutlined />
                    </div>
                  </template>
                  <a-card-meta title="JUnit XML" description="标准 JUnit XML 格式，可用于 CI/CD 流水线集成（Jenkins/GitLab等）" />
                </a-card>
              </a-col>
            </a-row>
          </a-card>
        </a-tab-pane>
      </a-tabs>
    </div>

    <div v-else class="loading-container">
      <a-spin size="large" tip="加载报告中..." />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { FileTextOutlined, CodeOutlined } from '@ant-design/icons-vue'
import {
  testPlanExecutionsApi,
  testPlansApi,
  getItemTypeLabel, getItemTypeColor, getItemTypeDetailLabel,
  type TestPlanExecution,
  type TestPlanExecutionResult,
} from '@/api/testPlans'
import { formatDateTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId) || 0
const planId = Number(route.params.planId)
const executionId = Number(route.params.executionId)

const execution = ref<TestPlanExecution | null>(null)
const results = ref<TestPlanExecutionResult[]>([])
const activeTab = ref('overview')
const detailTabs = ref<Record<number, string>>({})

const failedResults = computed(() =>
  results.value.filter(r => r.status === 'failed' || r.status === 'error')
)

const totalDuration = computed(() => {
  if (!execution.value?.started_at || !execution.value?.finished_at) return '-'
  const start = new Date(execution.value.started_at).getTime()
  const end = new Date(execution.value.finished_at).getTime()
  const ms = end - start
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}分${sec}秒`
})

const logs = computed(() => {
  const logList: { time: string; level: string; message: string }[] = []
  if (!execution.value) return logList

  logList.push({
    time: formatDateTime(execution.value.started_at) || '',
    level: 'INFO',
    message: `测试计划 "${execution.value.plan_name}" 开始执行，共 ${execution.value.total_items} 个节点`,
  })

  results.value.forEach(r => {
    const time = formatDateTime(r.started_at) || ''
    if (r.status === 'passed') {
      logList.push({ time, level: 'INFO', message: `节点 "${r.item_name}" 执行通过，耗时 ${r.duration_ms}ms` })
    } else if (r.status === 'failed') {
      logList.push({ time, level: 'ERROR', message: `节点 "${r.item_name}" 执行失败: ${r.error_message || '断言失败'}` })
    } else if (r.status === 'skipped') {
      logList.push({ time, level: 'WARN', message: `节点 "${r.item_name}" 被跳过: ${r.error_message || ''}` })
    } else if (r.status === 'error') {
      logList.push({ time, level: 'ERROR', message: `节点 "${r.item_name}" 执行错误: ${r.error_message}` })
    }
  })

  if (execution.value.finished_at) {
    logList.push({
      time: formatDateTime(execution.value.finished_at),
      level: 'INFO',
      message: `测试计划执行完成，通过 ${execution.value.passed_count}，失败 ${execution.value.failed_count}，跳过 ${execution.value.skipped_count}，通过率 ${execution.value.pass_rate}%`,
    })
  }

  return logList
})

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
  }
  return map[status] || 'default'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function getResultStatusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    passed: 'success',
    failed: 'error',
    skipped: 'warning',
    error: 'error',
  }
  return map[status] || 'default'
}

function getResultStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    passed: '通过',
    failed: '失败',
    skipped: '跳过',
    error: '错误',
  }
  return map[status] || status
}

function getDetailTab(id: number) {
  return detailTabs.value[id] || 'request'
}

function setDetailTab(id: number, key: string) {
  detailTabs.value[id] = key
}

function formatJson(data: any) {
  if (!data) return '{}'
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

function stringify(v: any): string {
  if (v === undefined || v === null) return '-'
  if (typeof v === 'object') {
    try { return JSON.stringify(v) } catch { return String(v) }
  }
  return String(v)
}

function hasAssertionText(a: any): boolean {
  return !!(a && (a.assert_type || a.assert_target || a.expected_value !== undefined))
}

function hasActualValue(a: any): boolean {
  return !!(a && a.actual_value !== undefined && a.actual_value !== null && a.actual_value !== '')
}

function assertTypeLabel(t: string): string {
  const map: Record<string, string> = {
    status_code: '状态码',
    response_time: '响应时间',
    jsonpath: 'JSONPath',
    xpath: 'XPath',
    header: '响应头',
    contains: '包含',
    equals: '等于',
    regex: '正则匹配',
    script: '脚本断言',
    in_range: '范围',
    not_equals: '不等于',
    not_contains: '不包含',
    greater_than: '大于',
    less_than: '小于',
  }
  return map[t || ''] || (t || '断言')
}

async function loadReport() {
  try {
    const res = await testPlanExecutionsApi.detail(executionId)
    execution.value = res.execution
    results.value = res.results
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载报告失败')
  }
}

async function exportHtml() {
  try {
    await testPlanExecutionsApi.downloadHtml(executionId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导出失败')
  }
}

async function exportJunit() {
  try {
    await testPlanExecutionsApi.downloadJunit(executionId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导出失败')
  }
}

async function reRun() {
  if (!planId) return
  try {
    const res = await testPlanExecutionsApi.run(projectId, planId)
    message.success('已重新启动执行')
    router.push(`/projects/${projectId}/test-plans/${planId}/run/${res.execution_id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
  }
}

function goBack() {
  if (projectId) {
    router.push(`/projects/${projectId}/plans`)
  } else {
    router.back()
  }
}

onMounted(() => {
  loadReport()
})
</script>

<style scoped>
.test-plan-report {
  padding: 16px;
}
.report-content {
  margin-top: 16px;
}
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}
.chart-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 16px 0;
}
.pie-chart {
  flex-shrink: 0;
}
.legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.failed-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.failed-rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff1f0;
  color: #ff4d4f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  flex-shrink: 0;
}
.failed-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.collapse-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.result-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #1890ff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.result-name {
  flex: 1;
  font-weight: 500;
}
.result-duration {
  color: #8c8c8c;
  font-size: 12px;
}
.result-retry {
  color: #faad14;
  font-size: 12px;
}
.result-detail {
  padding: 8px 0;
}
.code-block {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.assertion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.assertion-text {
  font-size: 13px;
  flex: 1;
}
.assertion-actual {
  font-size: 12px;
  color: #8c8c8c;
}
.log-container {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  max-height: 500px;
  overflow-y: auto;
}
.log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
  align-items: flex-start;
}
.log-time {
  color: #858585;
  flex-shrink: 0;
}
.log-message {
  flex: 1;
  word-break: break-all;
}
.log-empty {
  text-align: center;
  color: #858585;
  padding: 40px 0;
}
.export-card {
  cursor: pointer;
  text-align: center;
}
.export-icon {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  color: #fff;
}
.html-icon {
  background: linear-gradient(135deg, #e44d26, #f16529);
}
.xml-icon {
  background: linear-gradient(135deg, #007acc, #00a2e8);
}
</style>
