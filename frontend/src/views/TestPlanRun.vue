<template>
  <div class="test-plan-run">
    <a-page-header :title="`执行进度 - ${execution?.plan_name || '测试计划'}`" @back="goBack">
      <template #extra>
        <a-button @click="goBack">返回列表</a-button>
        <a-button
          v-if="execution && (execution.status === 'pending' || execution.status === 'running')"
          danger
          @click="handleCancel"
        >
          取消执行
        </a-button>
        <a-button
          v-if="execution && execution.status !== 'pending' && execution.status !== 'running'"
          type="primary"
          @click="viewReport"
        >
          查看报告
        </a-button>
      </template>
    </a-page-header>

    <div v-if="execution" class="run-content">
      <!-- 概览统计 -->
      <a-row :gutter="16" style="margin-bottom: 16px">
        <a-col :span="6">
          <a-card size="small">
            <a-statistic
              title="执行状态"
              :value="getStatusText(execution?.status || '')"
              :value-style="{ color: getStatusColor(execution?.status || ''), fontSize: '18px' }"
            />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic title="总节点数" :value="execution.total_items" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic title="通过 / 失败" :value="`${execution.passed_count} / ${execution.failed_count}`" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic title="通过率" :value="execution.pass_rate" suffix="%" />
          </a-card>
        </a-col>
      </a-row>

      <!-- 进度条 -->
      <a-card size="small" style="margin-bottom: 16px">
        <a-progress
          :percent="progressPercent"
          :status="progressStatus"
          :format="() => `${completedCount}/${execution?.total_items ?? 0}`"
        />
        <div class="time-info">
          <span v-if="execution.started_at">开始时间: {{ formatDateTime(execution.started_at) }}</span>
          <span v-if="execution.finished_at" style="margin-left: 24px">
            结束时间: {{ formatDateTime(execution.finished_at) }}
          </span>
          <span v-if="execution.started_at && !execution.finished_at" style="margin-left: 24px">
            已耗时: {{ elapsedTime }}
          </span>
        </div>
      </a-card>

      <!-- 节点执行列表 -->
      <a-card size="small" title="节点执行详情">
        <a-table
          :columns="nodeColumns"
          :data-source="results"
          :loading="loading"
          :pagination="false"
          row-key="id"
          size="small"
          :locale="{ emptyText: '暂无执行节点' }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'index'">
              {{ record.sort_order + 1 }}
            </template>
            <template v-else-if="column.key === 'item_type'">
              <a-tag :color="record.item_type === 'case' ? 'blue' : 'purple'">
                {{ record.item_type === 'case' ? '用例' : '场景' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="getResultStatusColor(record.status)">
                {{ getResultStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'duration_ms'">
              {{ record.duration_ms }} ms
            </template>
            <template v-else-if="column.key === 'retry_count'">
              {{ record.retry_count > 0 ? `${record.retry_count}次` : '-' }}
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button
                v-if="record.status !== 'pending' && record.status !== 'running'"
                type="link"
                size="small"
                @click="showDetail(record)"
              >
                详情
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 错误信息 -->
      <a-alert
        v-if="execution.error_message"
        type="error"
        show-icon
        :message="execution.error_message"
        style="margin-top: 16px"
      />
    </div>

    <!-- 节点详情弹窗 -->
    <a-modal
      v-model:open="detailVisible"
      title="节点执行详情"
      width="800px"
      :footer="null"
    >
      <div v-if="currentResult">
        <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
          <a-descriptions-item label="节点名称">{{ currentResult.item_name }}</a-descriptions-item>
          <a-descriptions-item label="节点类型">
            {{ currentResult.item_type === 'case' ? '接口用例' : '场景编排' }}
          </a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="getResultStatusColor(currentResult.status)">
              {{ getResultStatusText(currentResult.status) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="耗时">{{ currentResult.duration_ms }} ms</a-descriptions-item>
          <a-descriptions-item label="重试次数">{{ currentResult.retry_count }}</a-descriptions-item>
          <a-descriptions-item label="执行顺序">{{ currentResult.sort_order + 1 }}</a-descriptions-item>
        </a-descriptions>

        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="request" tab="请求信息">
            <pre class="code-block">{{ formatJson(currentResult.request_data) }}</pre>
          </a-tab-pane>
          <a-tab-pane key="response" tab="响应信息">
            <pre class="code-block">{{ formatJson(currentResult.response_data) }}</pre>
          </a-tab-pane>
          <a-tab-pane key="assertions" tab="断言结果">
            <div v-if="currentResult.assertions && currentResult.assertions.length > 0">
              <div
                v-for="(a, idx) in currentResult.assertions"
                :key="idx"
                class="assertion-item"
              >
                <a-tag :color="a.passed ? 'green' : 'red'">
                  {{ a.passed ? '通过' : '失败' }}
                </a-tag>
                <span class="assertion-text">
                  {{ a.assert_type }}: {{ a.assert_target }} {{ a.operator }} {{ a.expected_value }}
                </span>
                <span v-if="a.actual_value !== undefined" class="assertion-actual">
                  实际值: {{ a.actual_value }}
                </span>
              </div>
            </div>
            <a-empty v-else description="无断言" />
          </a-tab-pane>
          <a-tab-pane key="error" tab="错误信息" v-if="currentResult.error_message">
            <a-alert type="error" :message="currentResult.error_message" />
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  testPlanExecutionsApi,
  type TestPlanExecution,
  type TestPlanExecutionResult,
} from '@/api/testPlans'
import { formatDateTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const planId = Number(route.params.planId)
const executionId = Number(route.params.executionId)

const loading = ref(false)
const execution = ref<TestPlanExecution | null>(null)
const results = ref<TestPlanExecutionResult[]>([])
const detailVisible = ref(false)
const currentResult = ref<TestPlanExecutionResult | null>(null)
const activeTab = ref('request')
let pollTimer: number | null = null
let elapsedTimer: number | null = null
const elapsedSeconds = ref(0)

const nodeColumns = [
  { title: '序号', key: 'index', width: 60 },
  { title: '节点名称', dataIndex: 'item_name', key: 'item_name' },
  { title: '类型', key: 'item_type', width: 80 },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时', key: 'duration_ms', width: 100 },
  { title: '重试', key: 'retry_count', width: 80 },
  { title: '操作', key: 'action', width: 80 },
]

const completedCount = computed(() => {
  if (!execution.value) return 0
  return execution.value.passed_count + execution.value.failed_count + execution.value.skipped_count
})

const progressPercent = computed(() => {
  if (!execution.value || execution.value.total_items === 0) return 0
  return Math.round((completedCount.value / execution.value.total_items) * 100)
})

const progressStatus = computed(() => {
  if (!execution.value) return 'active'
  if (execution.value.status === 'running') return 'active'
  if (execution.value.status === 'completed') return 'success'
  if (execution.value.status === 'failed') return 'exception'
  if (execution.value.status === 'cancelled') return 'normal'
  return 'active'
})

const elapsedTime = computed(() => {
  const s = elapsedSeconds.value
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}分${sec}秒`
})

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    pending: '#faad14',
    running: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
    cancelled: '#8c8c8c',
  }
  return map[status] || '#8c8c8c'
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

function formatJson(data: any) {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

async function loadExecution() {
  try {
    const [statusRes, detailRes] = await Promise.all([
      testPlanExecutionsApi.status(executionId),
      testPlanExecutionsApi.detail(executionId),
    ])
    execution.value = { ...execution.value, ...statusRes } as TestPlanExecution
    results.value = detailRes.results
  } catch (e: any) {
    console.error('加载执行状态失败', e)
  }
}

function startPolling() {
  pollTimer = window.setInterval(async () => {
    await loadExecution()
    if (
      execution.value &&
      ['completed', 'failed', 'cancelled'].includes(execution.value.status)
    ) {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startElapsedTimer() {
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value++
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function showDetail(record: TestPlanExecutionResult) {
  currentResult.value = record
  activeTab.value = 'request'
  detailVisible.value = true
}

async function handleCancel() {
  Modal.confirm({
    title: '确认取消执行？',
    content: '取消后未执行的节点将被标记为跳过',
    okText: '确认取消',
    okType: 'danger',
    cancelText: '继续执行',
    onOk: async () => {
      try {
        await testPlanExecutionsApi.cancel(executionId)
        message.success('已取消执行')
        await loadExecution()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '取消失败')
      }
    },
  })
}

function viewReport() {
  router.push(`/test-plans/${planId}/report/${executionId}`)
}

function goBack() {
  router.push(`/projects/${projectId}/plans`)
}

watch(
  () => execution.value?.status,
  (newStatus) => {
    if (newStatus && ['completed', 'failed', 'cancelled'].includes(newStatus)) {
      stopElapsedTimer()
    }
  }
)

onMounted(async () => {
  loading.value = true
  await loadExecution()
  loading.value = false
  if (
    execution.value &&
    ['pending', 'running'].includes(execution.value.status)
  ) {
    startPolling()
    startElapsedTimer()
  }
})

onUnmounted(() => {
  stopPolling()
  stopElapsedTimer()
})
</script>

<style scoped>
.test-plan-run {
  padding: 16px;
}
.run-content {
  margin-top: 16px;
}
.time-info {
  margin-top: 8px;
  font-size: 12px;
  color: #8c8c8c;
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
</style>
