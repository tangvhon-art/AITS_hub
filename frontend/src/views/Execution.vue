<template>
  <div class="page-container">
    <div class="page-header">
      <h2>UI 自动化执行</h2>
    </div>

    <a-row :gutter="24">
      <!-- 左侧：执行配置 -->
      <a-col :xs="24" :lg="8">
        <a-card title="执行配置">
          <a-form layout="vertical">
            <a-alert
              v-if="currentCaseTitle"
              :message="`关联用例：${currentCaseTitle}`"
              type="info"
              :show-icon="true"
              style="margin-bottom: 16px"
            />
            <a-form-item label="目标 URL">
              <a-input v-model:value="targetUrl" placeholder="https://example.com" />
            </a-form-item>
            <a-form-item label="测试指令">
              <a-textarea
                v-model:value="instruction"
                :rows="6"
                placeholder="例如：打开登录页，输入用户名 admin，密码 123456，点击登录按钮，验证是否登录成功"
              />
            </a-form-item>
            <a-form-item label="模型配置">
              <a-select
                v-model:value="selectedLLMConfig"
                placeholder="使用默认模型"
                allow-clear
                :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
              />
            </a-form-item>
            <a-form-item label="无头模式">
              <a-switch v-model:checked="headless" />
            </a-form-item>
            <a-form-item>
              <a-button
                type="primary"
                :loading="running"
                @click="startExecution"
                :disabled="!instruction.trim()"
                style="margin-right: 8px"
              >
                <template #icon>
                  <PlayCircleOutlined />
                </template>
                开始执行
              </a-button>
              <a-button v-if="running" danger @click="stopExecution">停止</a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>

      <!-- 右侧：执行日志 -->
      <a-col :xs="24" :lg="16">
        <a-card>
          <template #title>
            <div class="card-header-title">
              <span>执行日志</span>
              <a-tag v-if="running" color="processing">执行中...</a-tag>
              <a-tag v-else-if="lastStatus === 'passed'" color="success">通过</a-tag>
              <a-tag v-else-if="lastStatus === 'failed'" color="error">失败</a-tag>
              <a-tag v-else-if="lastStatus === 'error'" color="error">错误</a-tag>
            </div>
          </template>

          <div class="log-container" ref="logContainer">
            <div v-if="executionLog.length === 0" class="empty-log">
              <a-empty description="等待执行..." :image-style="{ height: 60 }" />
            </div>
            <div v-for="(log, idx) in executionLog" :key="idx" class="log-item" :class="log.status">
              <div class="log-header">
                <span class="log-step">步骤 {{ log.step }}</span>
                <span class="log-action">{{ log.action }}</span>
              </div>
              <div v-if="log.thought" class="log-thought">💡 {{ log.thought }}</div>
              <div class="log-detail">{{ log.detail }}</div>
              <div v-if="log.result" class="log-result">
                结果: {{ log.result }}
              </div>
            </div>
          </div>

          <div v-if="finalResult" class="final-result" :class="lastStatus">
            <h4>执行完成</h4>
            <p>状态: {{ lastStatus === 'passed' ? '通过' : lastStatus === 'failed' ? '失败' : '错误' }}</p>
            <p>耗时: {{ duration }} 秒</p>
            <p>步骤数: {{ totalSteps }}</p>
          </div>

          <div v-if="screenshotUrl" class="screenshot-section">
            <h4>执行截图</h4>
            <img :src="'/api/' + screenshotUrl" alt="执行截图" class="screenshot-img" />
          </div>
        </a-card>

        <!-- 历史执行记录 -->
        <a-card title="历史执行记录" style="margin-top: 24px">
          <a-spin :spinning="runsLoading">
            <a-table
              :columns="runColumns"
              :data-source="runs"
              :pagination="runsPagination"
              @change="handleRunsTableChange"
              row-key="id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="runStatusColor(record.status)">{{ runStatusLabel(record.status) }}</a-tag>
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" size="small" @click="viewRunLog(record)">
                    查看日志
                  </a-button>
                </template>
              </template>
            </a-table>
          </a-spin>
        </a-card>
      </a-col>
    </a-row>

    <!-- 历史执行日志弹窗 -->
    <a-modal
      v-model:open="showLogModal"
      :title="`执行日志 #${selectedRunId}`"
      :footer="null"
      width="800px"
    >
      <a-spin :spinning="logLoading">
        <div v-if="selectedRunDetail" style="margin-bottom: 12px">
          <a-descriptions :column="3" size="small">
            <a-descriptions-item label="状态">
              <a-tag :color="runStatusColor(selectedRunDetail.status)">{{ runStatusLabel(selectedRunDetail.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="耗时">{{ selectedRunDetail.duration }}s</a-descriptions-item>
            <a-descriptions-item label="执行时间">{{ selectedRunDetail.started_at || selectedRunDetail.created_at }}</a-descriptions-item>
          </a-descriptions>
          <a-alert
            v-if="selectedRunDetail.error_message"
            type="error"
            :message="selectedRunDetail.error_message"
            show-icon
            style="margin-top: 8px"
          />
        </div>
        <div class="log-container" style="max-height: 500px">
          <div v-if="historyLog.length === 0" class="empty-log">
            <a-empty description="无执行日志" :image-style="{ height: 60 }" />
          </div>
          <div v-for="(log, idx) in historyLog" :key="idx" class="log-item" :class="log.status">
            <div class="log-header">
              <span class="log-step">步骤 {{ idx + 1 }}</span>
              <span class="log-action">{{ log.action }}</span>
              <span v-if="log.duration != null" class="log-duration">{{ log.duration }}s</span>
            </div>
            <div v-if="log.thought" class="log-thought">💡 {{ log.thought }}</div>
            <div class="log-detail">{{ log.observation || log.detail || JSON.stringify(log.params || {}) }}</div>
          </div>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'
import { runExecution, getExecutionRunStatus, getExecutionRuns, getExecutionRun } from '@/api/execution'
import { getLLMConfigs } from '@/api/llm'

const route = useRoute()
const projectId = Number(route.params.id)

const targetUrl = ref('')
const instruction = ref('')
const headless = ref(true)
const selectedLLMConfig = ref<number | null>(null)
const llmConfigs = ref<any[]>([])
const currentCaseId = ref<number | null>(null)
const currentCaseTitle = ref('')

const running = ref(false)
const executionLog = ref<any[]>([])
const lastStatus = ref('')
const finalResult = ref('')
const duration = ref(0)
const totalSteps = ref(0)
const screenshotUrl = ref('')
const logContainer = ref<HTMLElement>()

const runs = ref<any[]>([])

const runsPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

function handleRunsTableChange(pag: any) {
  runsPagination.current = pag.current
  runsPagination.pageSize = pag.pageSize
}
const runsLoading = ref(false)

const runColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '耗时(秒)', dataIndex: 'duration', key: 'duration', width: 100 },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 100 },
]

// 轮询控制
let pollTimer: ReturnType<typeof setInterval> | null = null
let currentRunId: number | null = null

// 历史日志查看
const showLogModal = ref(false)
const logLoading = ref(false)
const selectedRunId = ref<number>(0)
const selectedRunDetail = ref<any>(null)
const historyLog = ref<any[]>([])

function runStatusColor(status: string) {
  const map: Record<string, string> = {
    passed: 'success',
    failed: 'error',
    error: 'error',
    running: 'processing',
    pending: 'default'
  }
  return map[status] || 'default'
}

function runStatusLabel(status: string) {
  const map: Record<string, string> = {
    passed: '通过',
    failed: '失败',
    error: '错误',
    running: '执行中',
    pending: '等待中'
  }
  return map[status] || status
}

function normalizeStatus(status: string): string {
  if (['success', 'ok', 'pass', 'passed', 'complete', 'completed'].includes(status?.toLowerCase())) {
    return 'passed'
  } else if (['fail', 'failed', 'error'].includes(status?.toLowerCase())) {
    return 'failed'
  }
  return status
}

async function startExecution() {
  if (!instruction.value.trim()) {
    message.warning('请输入测试指令')
    return
  }

  running.value = true
  executionLog.value = []
  lastStatus.value = ''
  finalResult.value = ''
  screenshotUrl.value = ''

  try {
    const res = await runExecution(projectId, {
      instruction: instruction.value,
      target_url: targetUrl.value,
      headless: headless.value,
      llm_config_id: selectedLLMConfig.value || undefined,
      case_id: currentCaseId.value || undefined,
    })
    currentRunId = res.run_id
    message.success('执行已提交，正在运行...')
    startPolling()
  } catch (e: any) {
    running.value = false
    message.error('提交执行失败')
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(pollExecutionStatus, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollExecutionStatus() {
  if (!currentRunId) return

  try {
    const data = await getExecutionRunStatus(projectId, currentRunId)

    // 更新执行日志（增量替换）
    if (data.execution_log && data.execution_log.length > 0) {
      executionLog.value = data.execution_log
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
    }

    if (data.completed) {
      stopPolling()
      currentRunId = null
      running.value = false

      const status = normalizeStatus(data.status)
      lastStatus.value = status
      finalResult.value = data.actual_result
      duration.value = data.duration || 0
      totalSteps.value = data.execution_log?.length || 0
      screenshotUrl.value = data.screenshot_url || ''

      executionLog.value.push({
        step: executionLog.value.length + 1,
        action: status === 'passed' ? '完成' : '失败',
        detail: data.actual_result || data.error_message || '',
        status: status,
      })

      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })

      fetchRuns()
    }
  } catch (e: any) {
    // 单次轮询失败不中断
  }
}

function stopExecution() {
  stopPolling()
  currentRunId = null
  running.value = false
  message.info('已停止轮询（后端任务仍在运行，可在历史记录中查看结果）')
}

async function fetchRuns() {
  runsLoading.value = true
  try {
    runs.value = await getExecutionRuns(projectId)
    runsPagination.total = runs.value.length
  } finally {
    runsLoading.value = false
  }
}

async function viewRunLog(record: any) {
  selectedRunId.value = record.id
  showLogModal.value = true
  logLoading.value = true
  historyLog.value = []
  selectedRunDetail.value = null
  try {
    const detail = await getExecutionRun(projectId, record.id)
    selectedRunDetail.value = detail
    // 解析执行日志
    let logData = detail.execution_log
    if (typeof logData === 'string' && logData) {
      try {
        logData = JSON.parse(logData)
      } catch {
        logData = []
      }
    }
    historyLog.value = Array.isArray(logData) ? logData : []
  } catch (e: any) {
    message.error('加载执行日志失败')
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  // 从用例页面跳转过来时，自动填充用例信息
  if (route.query.caseId) {
    currentCaseId.value = Number(route.query.caseId)
  }
  if (route.query.caseTitle) {
    currentCaseTitle.value = route.query.caseTitle as string
  }
  if (route.query.instruction) {
    instruction.value = decodeURIComponent(route.query.instruction as string)
  }
  getLLMConfigs().then(data => { llmConfigs.value = data })
  fetchRuns()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.card-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-container {
  max-height: 420px;
  overflow-y: auto;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 16px;
  min-height: 240px;
}

.empty-log {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.log-item {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #2d2d2d;
  border-radius: 6px;
  border-left: 3px solid #1677ff;
}

.log-item.passed {
  border-left-color: #52c41a;
}

.log-item.failed,
.log-item.error {
  border-left-color: #ff4d4f;
}

.log-header {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
}

.log-step {
  color: #569cd6;
  font-weight: 600;
  font-size: 13px;
}

.log-action {
  color: #6a9955;
  font-size: 13px;
}

.log-duration {
  color: #dcdcaa;
  font-size: 12px;
  margin-left: auto;
}

.log-thought {
  color: #ce9178;
  font-size: 13px;
  margin-bottom: 6px;
}

.log-detail {
  color: #d4d4d4;
  font-size: 13px;
  word-break: break-all;
  line-height: 1.6;
}

.log-result {
  margin-top: 6px;
  font-weight: 600;
  color: #569cd6;
}

.final-result {
  margin-top: 16px;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.final-result.passed {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.final-result.failed,
.final-result.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.final-result h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: rgba(0, 0, 0, 0.88);
}

.final-result p {
  margin: 4px 0;
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
}

.screenshot-section {
  margin-top: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}

.screenshot-section h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.88);
}

.screenshot-img {
  width: 100%;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  cursor: pointer;
}
</style>
