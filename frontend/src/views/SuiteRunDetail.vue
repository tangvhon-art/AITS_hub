<template>
  <div class="suite-run-detail">
    <div class="page-header">
      <div>
        <a-button @click="$router.back" style="margin-bottom: 12px">
          <LeftOutlined /> 返回
        </a-button>
        <h2>编排执行详情 #{{ runId }}</h2>
      </div>
      <a-space>
        <a-tag v-if="runInfo" :color="getStatusColor(runInfo.status)" style="font-size: 14px; padding: 4px 12px">
          {{ getStatusText(runInfo.status) }}
        </a-tag>
        <a-button @click="loadData" :loading="loading">
          <ReloadOutlined /> 刷新
        </a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <a-card v-if="runInfo" :bordered="false" style="margin-bottom: 16px">
        <a-row :gutter="24">
          <a-col :span="6">
            <a-statistic title="总步骤" :value="runInfo.total_steps || 0" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="通过" :value="runInfo.passed_steps || 0" :value-style="{ color: '#52c41a' }" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="失败" :value="runInfo.failed_steps || 0" :value-style="{ color: '#ff4d4f' }" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="跳过" :value="runInfo.skipped_steps || 0" :value-style="{ color: '#faad14' }" />
          </a-col>
        </a-row>
        <a-divider />
        <a-descriptions :column="3" size="small">
          <a-descriptions-item label="通过率">
            {{ runInfo.pass_rate != null ? runInfo.pass_rate.toFixed(1) + '%' : '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="总耗时">{{ runInfo.total_duration }}s</a-descriptions-item>
          <a-descriptions-item label="触发方式">{{ getTriggerText(runInfo.trigger_type) }}</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ $formatDateTime(runInfo.started_at) }}</a-descriptions-item>
          <a-descriptions-item label="完成时间">{{ $formatDateTime(runInfo.completed_at) }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ runInfo.executed_by || '-' }}</a-descriptions-item>
        </a-descriptions>
        <a-alert
          v-if="runInfo.error_message"
          type="error"
          message="执行错误"
          :description="runInfo.error_message"
          show-icon
          style="margin-top: 12px"
        />
      </a-card>

      <a-card title="步骤执行结果" :bordered="false">
        <a-table
          :columns="columns"
          :data-source="results"
          :pagination="false"
          :loading="loading"
          row-key="id"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'duration'">
              {{ record.duration ? record.duration + 's' : '-' }}
            </template>
            <template v-else-if="column.key === 'retry'">
              <span v-if="record.retry_count > 0" style="color: #faad14">重试 {{ record.retry_count }} 次</span>
              <span v-else>-</span>
            </template>
            <template v-else-if="column.key === 'error'">
              <a-tooltip v-if="record.error_message" :title="record.error_message">
                <span style="color: #ff4d4f; cursor: pointer">{{ record.error_message.slice(0, 50) }}...</span>
              </a-tooltip>
              <span v-else>-</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space>
                <a-button v-if="record.execution_log" type="link" size="small" @click="viewStepLog(record)">
                  日志
                </a-button>
                <a-button v-if="record.run_id" type="link" size="small" @click="viewRunDetail(record.run_id)">
                  执行
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
        <a-empty v-if="results.length === 0" description="暂无执行结果" />
      </a-card>
    </a-spin>

    <!-- 步骤执行日志弹窗 -->
    <a-modal
      v-model:open="showStepLogModal"
      :title="`步骤执行日志 - ${selectedStepName}`"
      :footer="null"
      width="720px"
    >
      <div class="log-container">
        <div v-if="stepLogList.length === 0" class="empty-log">
          <a-empty description="无执行日志" :image-style="{ height: 60 }" />
        </div>
        <div v-for="(log, idx) in stepLogList" :key="idx" class="log-item" :class="log.status">
          <div class="log-header">
            <span class="log-step">步骤 {{ idx + 1 }}</span>
            <span class="log-action">{{ log.action }}</span>
            <span v-if="log.duration != null" class="log-duration">{{ log.duration }}s</span>
          </div>
          <div class="log-detail">{{ log.detail || log.observation || JSON.stringify(log.params || {}) }}</div>
          <div v-if="log.error" class="log-error">{{ log.error }}</div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LeftOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { getSuiteRun, getSuiteRunResults, type SuiteRun, type SuiteRunResult } from '@/api/automationSuites'

const route = useRoute()
const router = useRouter()
const runId = Number(route.params.runId)

const loading = ref(false)
const runInfo = ref<SuiteRun | null>(null)
const results = ref<SuiteRunResult[]>([])
let refreshTimer: number | null = null

const columns = [
  { title: '序号', dataIndex: 'sort_order', width: 60 },
  { title: '步骤名称', dataIndex: 'step_name' },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '重试', key: 'retry', width: 80 },
  { title: '错误信息', key: 'error', ellipsis: true },
  { title: '操作', key: 'action', width: 120 },
]

const isRunning = computed(() => {
  return runInfo.value?.status === 'running' || runInfo.value?.status === 'pending'
})

async function loadData() {
  loading.value = true
  try {
    runInfo.value = await getSuiteRun(Number(route.params.id), runId)
    results.value = await getSuiteRunResults(Number(route.params.id), runId)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = window.setInterval(() => {
    if (isRunning.value) {
      loadData()
    } else {
      stopAutoRefresh()
    }
  }, 3000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function viewRunDetail(runId: number) {
  router.push(`/projects/${route.params.id}/execution?run_id=${runId}`)
}

// 步骤日志查看
const showStepLogModal = ref(false)
const selectedStepName = ref('')
const stepLogList = ref<any[]>([])

function viewStepLog(record: any) {
  selectedStepName.value = record.step_name || ''
  showStepLogModal.value = true
  let logData = record.execution_log
  if (typeof logData === 'string' && logData) {
    try {
      logData = JSON.parse(logData)
    } catch {
      logData = []
    }
  }
  stepLogList.value = Array.isArray(logData) ? logData : []
}

function getStatusColor(status?: string) {
  const map: Record<string, string> = {
    passed: 'green', failed: 'red', partial: 'orange',
    running: 'blue', pending: 'default', skipped: 'default'
  }
  return map[status || ''] || 'default'
}

function getStatusText(status?: string) {
  const map: Record<string, string> = {
    passed: '通过', failed: '失败', partial: '部分通过',
    running: '执行中', pending: '等待中', skipped: '已跳过'
  }
  return map[status || ''] || status
}

function getTriggerText(type?: string) {
  const map: Record<string, string> = { manual: '手动触发', schedule: '定时触发', api: 'API触发' }
  return map[type || ''] || type
}

onMounted(() => {
  loadData()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.suite-run-detail { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

.log-container {
  max-height: 500px;
  overflow-y: auto;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 16px;
  min-height: 120px;
}
.empty-log {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 120px;
}
.log-item {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: #2d2d2d;
  border-radius: 6px;
  border-left: 3px solid #1677ff;
}
.log-item.passed { border-left-color: #52c41a; }
.log-item.failed { border-left-color: #ff4d4f; }
.log-header {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
  align-items: center;
}
.log-step { color: #569cd6; font-weight: 600; font-size: 13px; }
.log-action { color: #6a9955; font-size: 13px; }
.log-duration { color: #dcdcaa; font-size: 12px; margin-left: auto; }
.log-detail { color: #d4d4d4; font-size: 13px; word-break: break-all; line-height: 1.6; }
.log-error { color: #f48771; font-size: 13px; margin-top: 4px; }
</style>
