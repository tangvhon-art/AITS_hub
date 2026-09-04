<template>
  <div class="page-container">
    <PageHeader title="任务调度管理">
  <template #extra>
    <a-button type="primary" @click="openCreateModal">
        <template #icon>
          <PlusOutlined />
        </template>
        新建定时任务
      </a-button>
  </template>
</PageHeader><a-card>
      <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
        <!-- Tab1 定时任务配置管理 -->
        <a-tab-pane key="tasks" tab="定时任务配置">
          <SearchBar @search="handleTaskSearch" @reset="handleTaskReset">
            <a-form-item label="关键词">
              <a-input
                v-model:value="taskKeyword"
                allow-clear
                placeholder="任务名称/唯一Key/函数路径"
                style="width: 260px"
                @press-enter="handleTaskSearch"
              />
            </a-form-item>
            
          </SearchBar>

          <DataTable
            :columns="taskColumns"
            :data-source="tasks"
            :loading="taskLoading"
            @change="handleTaskTableChange"
            row-key="id"
            size="middle"
            :scroll="{ x: 1400 }"
          >
        :page="taskPagination.current"
        :page-size="taskPagination.pageSize"
        :total="taskPagination.total"
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'task'">
                <a-tooltip :title="record.task">
                  <span class="ellipsis-text">{{ record.task }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'schedule_type'">
                <a-tag :color="record.schedule_type === 'cron' ? 'purple' : 'blue'">
                  {{ record.schedule_type === 'cron' ? 'CRON' : '间隔' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'schedule_expr'">
                <span>{{ record.schedule_type === 'interval' ? `每 ${record.schedule_expr} 秒` : record.schedule_expr }}</span>
              </template>
              <template v-else-if="column.key === 'queue'">
                <a-tag>{{ record.queue }}</a-tag>
              </template>
              <template v-else-if="column.key === 'params'">
                <a-tooltip :title="buildParamsText(record)">
                  <span class="ellipsis-text">{{ buildParamsText(record) || '-' }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'enabled'">
                <a-switch
                  :checked="record.enabled"
                  checked-children="启用"
                  un-checked-children="禁用"
                  :loading="switchingId === record.id"
                  @change="(checked: boolean) => toggleEnabled(record, checked)"
                />
              </template>
              <template v-else-if="column.key === 'created_at'">
                {{ formatDateTime(record.created_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
                <a-button type="link" size="small" @click="runOnce(record)">手动执行</a-button>
                <a-button type="link" size="small" danger @click="deleteTask(record)">删除</a-button>
              </template>
            </template>
          </DataTable>
        </a-tab-pane>

        <!-- Tab2 任务执行日志查询 -->
        <a-tab-pane key="logs" tab="任务执行日志">
          <SearchBar @search="handleTaskSearch" @reset="handleTaskReset">
            <a-form-item label="时间范围">
              <a-range-picker
                v-model:value="logFilterDateRange"
                show-time
                :placeholder="['开始时间', '结束时间']"
              />
            </a-form-item>
            <a-form-item label="任务名称">
              <a-input
                v-model:value="logFilters.task_name"
                allow-clear
                placeholder="任务名称/唯一Key"
                style="width: 220px"
                @press-enter="handleLogSearch"
              />
            </a-form-item>
            <a-form-item label="执行状态">
              <a-select v-model:value="logFilters.state" allow-clear placeholder="全部" style="width: 130px">
                <a-select-option value="RUNNING">运行中</a-select-option>
                <a-select-option value="SUCCESS">成功</a-select-option>
                <a-select-option value="FAILURE">失败</a-select-option>
                <a-select-option value="TIMEOUT">超时</a-select-option>
              </a-select>
            </a-form-item>
            
          </SearchBar>

          <DataTable
            :columns="logColumns"
            :data-source="logs"
            :loading="logLoading"
            @change="handleLogTableChange"
            row-key="id"
            size="middle"
            :scroll="{ x: 1300 }"
          >
        :page="logPagination.current"
        :page-size="logPagination.pageSize"
        :total="logPagination.total"
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'task_name'">
                <a-tooltip :title="record.task_name">
                  <span class="ellipsis-text">{{ record.task_key || record.task_name }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'queue'">
                <a-tag>{{ record.queue }}</a-tag>
              </template>
              <template v-else-if="column.key === 'state'">
                <a-tag :color="getStateColor(record.state)">{{ getStateText(record.state) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'started_at'">
                {{ formatDateTime(record.started_at) }}
              </template>
              <template v-else-if="column.key === 'finished_at'">
                {{ formatDateTime(record.finished_at) }}
              </template>
              <template v-else-if="column.key === 'duration_ms'">
                {{ formatDuration(record.duration_ms) }}
              </template>
              <template v-else-if="column.key === 'exception'">
                <a-tooltip v-if="record.exception" :title="record.exception">
                  <span class="ellipsis-text exception-text">{{ record.exception }}</span>
                </a-tooltip>
                <span v-else>-</span>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" size="small" @click="showLogDetail(record)">查看详情</a-button>
              </template>
            </template>
          </DataTable>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 新增/编辑定时任务弹窗 -->
    <FormModal
      v-model:visible="showTaskModal"
      title="editingTask ? '编辑定时任务' : '新建定时任务'"
      :loading="taskSaving"
      width="640px"
      @ok="saveTask"
    >
      <a-form-item label="任务名称" required>
          <a-input v-model:value="taskForm.name" placeholder="例如：清理uploads目录" />
        </a-form-item>
        <a-form-item label="任务唯一标识" required>
          <a-input v-model:value="taskForm.task_key" placeholder="唯一不可重复，例如：cleanup-uploads" />
        </a-form-item>
        <a-form-item label="任务函数全路径" required>
          <a-input v-model:value="taskForm.task" placeholder="例如：app.tasks.cleanup_tasks.cleanup_uploads_task" />
        </a-form-item>
        <a-form-item label="调度类型" required>
          <a-radio-group v-model:value="taskForm.schedule_type">
            <a-radio value="interval">固定间隔秒数</a-radio>
            <a-radio value="cron">CRON表达式</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="taskForm.schedule_type === 'interval'" label="间隔秒数" required>
          <a-input-number v-model:value="intervalSeconds" :min="1" style="width: 100%" placeholder="例如：3600" />
        </a-form-item>
        <a-form-item v-else label="CRON表达式" required>
          <a-input v-model:value="taskForm.schedule_expr" placeholder="5段式：分 时 日 月 周，例如 0 2 * * *" />
        </a-form-item>
        <a-form-item label="执行队列" required>
          <a-select v-model:value="taskForm.queue">
            <a-select-option value="default">default</a-select-option>
            <a-select-option value="ai">ai</a-select-option>
            <a-select-option value="execution">execution</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="任务入参 args（JSON数组）">
          <a-textarea v-model:value="argsText" :rows="2" placeholder='例如：["arg1", 2]' @blur="formatJson('args')" />
        </a-form-item>
        <a-form-item label="任务入参 kwargs（JSON对象）">
          <a-textarea v-model:value="kwargsText" :rows="2" placeholder='例如：{"key": "value"}' @blur="formatJson('kwargs')" />
        </a-form-item>
        <a-form-item label="任务描述">
          <a-textarea v-model:value="taskForm.description" :rows="2" placeholder="可选描述" />
        </a-form-item>
        <a-form-item label="是否启用">
          <a-switch v-model:checked="taskForm.enabled" checked-children="启用" un-checked-children="禁用" />
        </a-form-item>
    </FormModal>

    <!-- 执行日志详情弹窗 -->
    <a-modal v-model:open="showLogModal" title="执行日志详情" width="700px" :footer="null">
      <div v-if="currentLog">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="任务名称" :span="2">{{ currentLog.task_name }}</a-descriptions-item>
          <a-descriptions-item label="任务ID">{{ currentLog.task_id }}</a-descriptions-item>
          <a-descriptions-item label="执行队列">{{ currentLog.queue || '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="getStateColor(currentLog.state)">{{ getStateText(currentLog.state) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ formatDuration(currentLog.duration_ms) }}</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ formatDateTime(currentLog.started_at) }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ formatDateTime(currentLog.finished_at) }}</a-descriptions-item>
        </a-descriptions>
        <a-divider>任务参数</a-divider>
        <pre class="detail-json">args: {{ JSON.stringify(currentLog.args || [], null, 2) }}
kwargs: {{ JSON.stringify(currentLog.kwargs || {}, null, 2) }}</pre>
        <template v-if="currentLog.exception">
          <a-divider>异常摘要</a-divider>
          <a-alert :message="currentLog.exception" type="error" show-icon />
        </template>
        <template v-if="currentLog.traceback">
          <a-divider>错误堆栈</a-divider>
          <pre class="detail-json">{{ currentLog.traceback }}</pre>
        </template>
        <a-empty v-if="!currentLog.exception && !currentLog.traceback" description="任务执行正常，无异常信息" />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { formatDateTime } from '@/utils/date'
import {
  getBeatTasks,
  createBeatTask,
  updateBeatTask,
  deleteBeatTask,
  setBeatTaskStatus,
  runBeatTaskOnce,
  getBeatTaskLogs,
  getBeatTaskLogDetail,
  type BeatTask,
  type BeatTaskLog
} from '@/api/celeryBeat'
import PageHeader from '@/components/PageHeader.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import SearchBar from '@/components/SearchBar.vue'

const activeTab = ref('tasks')

// ---------------------------------------------------------------------------
// Tab1 定时任务配置
// ---------------------------------------------------------------------------
const taskLoading = ref(false)
const taskSaving = ref(false)
const switchingId = ref<number | null>(null)
const tasks = ref<BeatTask[]>([])
const taskPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})

const showTaskModal = ref(false)
const editingTask = ref<BeatTask | null>(null)
const intervalSeconds = ref<number | null>(null)
const argsText = ref('')
const kwargsText = ref('')
const taskKeyword = ref<string | undefined>(undefined)
const taskForm = reactive({
  name: '',
  task_key: '',
  task: '',
  schedule_type: 'interval' as 'interval' | 'cron',
  schedule_expr: '',
  queue: 'default',
  description: '',
  enabled: true
})

const taskColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', width: 160 },
  { title: '任务唯一Key', dataIndex: 'task_key', key: 'task_key', width: 180, ellipsis: true },
  { title: '任务函数全路径', dataIndex: 'task', key: 'task', width: 240, ellipsis: true },
  { title: '调度类型', dataIndex: 'schedule_type', key: 'schedule_type', width: 90 },
  { title: '调度表达式', dataIndex: 'schedule_expr', key: 'schedule_expr', width: 140 },
  { title: '执行队列', dataIndex: 'queue', key: 'queue', width: 100 },
  { title: '任务参数', key: 'params', width: 160, ellipsis: true },
  { title: '启用状态', dataIndex: 'enabled', key: 'enabled', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

function buildParamsText(record: BeatTask) {
  const parts: string[] = []
  if (record.args && record.args.length > 0) parts.push(`args=${JSON.stringify(record.args)}`)
  if (record.kwargs && Object.keys(record.kwargs).length > 0) parts.push(`kwargs=${JSON.stringify(record.kwargs)}`)
  return parts.join(' ')
}

async function loadTasks() {
  taskLoading.value = true
  try {
    const res = await getBeatTasks({
      page: taskPagination.current,
      page_size: taskPagination.pageSize,
      keyword: taskKeyword.value
    })
    tasks.value = res.items
    taskPagination.total = res.total
  } finally {
    taskLoading.value = false
  }
}

function handleTaskSearch() {
  taskPagination.current = 1
  loadTasks()
}

function handleTaskReset() {
  taskKeyword.value = undefined
  taskPagination.current = 1
  loadTasks()
}

function handleTaskTableChange(pag: any) {
  taskPagination.current = pag.current
  taskPagination.pageSize = pag.pageSize
  loadTasks()
}

function resetTaskForm() {
  Object.assign(taskForm, {
    name: '',
    task_key: '',
    task: '',
    schedule_type: 'interval',
    schedule_expr: '',
    queue: 'default',
    description: '',
    enabled: true
  })
  intervalSeconds.value = null
  argsText.value = ''
  kwargsText.value = ''
}

function openCreateModal() {
  editingTask.value = null
  resetTaskForm()
  showTaskModal.value = true
}

function openEditModal(record: BeatTask) {
  editingTask.value = record
  Object.assign(taskForm, {
    name: record.name,
    task_key: record.task_key || '',
    task: record.task,
    schedule_type: record.schedule_type,
    schedule_expr: record.schedule_expr,
    queue: record.queue,
    description: record.description || '',
    enabled: record.enabled
  })
  intervalSeconds.value = record.schedule_type === 'interval' ? Number(record.schedule_expr) || null : null
  argsText.value = record.args && record.args.length > 0 ? JSON.stringify(record.args, null, 2) : ''
  kwargsText.value = record.kwargs && Object.keys(record.kwargs).length > 0 ? JSON.stringify(record.kwargs, null, 2) : ''
  showTaskModal.value = true
}

/** JSON 输入框失焦时格式化并校验（复用系统 JSON.parse 校验方式） */
function formatJson(field: 'args' | 'kwargs') {
  const text = field === 'args' ? argsText.value : kwargsText.value
  if (!text.trim()) return
  try {
    const parsed = JSON.parse(text)
    if (field === 'args' && !Array.isArray(parsed)) {
      message.error('args 必须为 JSON 数组')
      return
    }
    if (field === 'kwargs' && (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null)) {
      message.error('kwargs 必须为 JSON 对象')
      return
    }
    if (field === 'args') argsText.value = JSON.stringify(parsed, null, 2)
    else kwargsText.value = JSON.stringify(parsed, null, 2)
  } catch {
    message.error(`${field} JSON 格式错误`)
  }
}

function validateTaskForm(): { args: any[]; kwargs: Record<string, any> } | null {
  if (!taskForm.name.trim()) {
    message.warning('请输入任务名称')
    return null
  }
  if (!taskForm.task_key.trim()) {
    message.warning('请输入任务唯一标识')
    return null
  }
  if (!taskForm.task.trim()) {
    message.warning('请输入任务函数全路径')
    return null
  }
  if (taskForm.schedule_type === 'interval') {
    if (!intervalSeconds.value || intervalSeconds.value <= 0) {
      message.warning('请输入正整数间隔秒数')
      return null
    }
    taskForm.schedule_expr = String(intervalSeconds.value)
  } else {
    const expr = taskForm.schedule_expr.trim()
    if (expr.split(/\s+/).length !== 5) {
      message.warning('CRON 表达式必须为 5 段：分 时 日 月 周')
      return null
    }
    taskForm.schedule_expr = expr
  }
  let args: any[] = []
  let kwargs: Record<string, any> = {}
  try {
    args = argsText.value.trim() ? JSON.parse(argsText.value) : []
    if (!Array.isArray(args)) {
      message.error('args 必须为 JSON 数组')
      return null
    }
  } catch {
    message.error('args JSON 格式错误')
    return null
  }
  try {
    kwargs = kwargsText.value.trim() ? JSON.parse(kwargsText.value) : {}
    if (typeof kwargs !== 'object' || Array.isArray(kwargs) || kwargs === null) {
      message.error('kwargs 必须为 JSON 对象')
      return null
    }
  } catch {
    message.error('kwargs JSON 格式错误')
    return null
  }
  return { args, kwargs }
}

async function saveTask() {
  const parsed = validateTaskForm()
  if (!parsed) return
  const payload = {
    ...taskForm,
    args: parsed.args,
    kwargs: parsed.kwargs
  }
  taskSaving.value = true
  try {
    if (editingTask.value) {
      await updateBeatTask({ id: editingTask.value.id, ...payload })
      message.success('更新成功，配置将自动生效')
    } else {
      await createBeatTask(payload)
      message.success('创建成功，配置将自动生效')
    }
    showTaskModal.value = false
    editingTask.value = null
    loadTasks()
  } finally {
    taskSaving.value = false
  }
}

async function toggleEnabled(record: BeatTask, checked: boolean) {
  switchingId.value = record.id
  try {
    await setBeatTaskStatus(record.id, checked)
    message.success(checked ? '已启用' : '已禁用')
    loadTasks()
  } finally {
    switchingId.value = null
  }
}

function runOnce(record: BeatTask) {
  Modal.confirm({
    title: '手动执行',
    content: `确定要立即执行一次任务「${record.name}」吗？不会影响原有定时规则。`,
    okText: '执行',
    cancelText: '取消',
    onOk: async () => {
      const res = await runBeatTaskOnce(record.id)
      message.success(`已触发，任务ID：${res.task_id}`)
    }
  })
}

function deleteTask(record: BeatTask) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除定时任务「${record.name}」吗？删除后将停止调度。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteBeatTask(record.id)
      message.success('删除成功')
      loadTasks()
    }
  })
}

// ---------------------------------------------------------------------------
// Tab2 任务执行日志
// ---------------------------------------------------------------------------
const logLoading = ref(false)
const logs = ref<BeatTaskLog[]>([])
const logPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})
const logFilters = reactive<{ task_name?: string; state?: string }>({
  task_name: undefined,
  state: undefined
})
const logFilterDateRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | undefined>(undefined)

const showLogModal = ref(false)
const currentLog = ref<BeatTaskLog | null>(null)
const logLoaded = ref(false)

const logColumns = [
  { title: '任务名称', dataIndex: 'task_name', key: 'task_name', width: 220, ellipsis: true },
  { title: '任务ID', dataIndex: 'task_id', key: 'task_id', width: 220, ellipsis: true },
  { title: '执行队列', dataIndex: 'queue', key: 'queue', width: 100 },
  { title: '执行状态', dataIndex: 'state', key: 'state', width: 90 },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at', width: 170 },
  { title: '结束时间', dataIndex: 'finished_at', key: 'finished_at', width: 170 },
  { title: '执行耗时', dataIndex: 'duration_ms', key: 'duration_ms', width: 100 },
  { title: '异常摘要', dataIndex: 'exception', key: 'exception', ellipsis: true },
  { title: '操作', key: 'action', width: 100, fixed: 'right' }
]

function getStateText(state: string) {
  const map: Record<string, string> = {
    RUNNING: '运行中',
    SUCCESS: '成功',
    FAILURE: '失败',
    TIMEOUT: '超时'
  }
  return map[state] || state
}

function getStateColor(state: string) {
  const map: Record<string, string> = {
    SUCCESS: 'green',
    FAILURE: 'red',
    RUNNING: 'blue',
    TIMEOUT: 'orange'
  }
  return map[state] || 'default'
}

function formatDuration(ms?: number | null) {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await getBeatTaskLogs({
      page: logPagination.current,
      page_size: logPagination.pageSize,
      task_name: logFilters.task_name,
      state: logFilters.state,
      start_time: logFilterDateRange.value?.[0]?.format('YYYY-MM-DD HH:mm:ss'),
      end_time: logFilterDateRange.value?.[1]?.format('YYYY-MM-DD HH:mm:ss')
    })
    logs.value = res.items
    logPagination.total = res.total
  } finally {
    logLoading.value = false
  }
}

function handleLogSearch() {
  logPagination.current = 1
  loadLogs()
}

function handleLogReset() {
  logFilters.task_name = undefined
  logFilters.state = undefined
  logFilterDateRange.value = undefined
  logPagination.current = 1
  loadLogs()
}

function handleLogTableChange(pag: any) {
  logPagination.current = pag.current
  logPagination.pageSize = pag.pageSize
  loadLogs()
}

async function showLogDetail(record: BeatTaskLog) {
  currentLog.value = record
  showLogModal.value = true
  try {
    currentLog.value = await getBeatTaskLogDetail(record.task_id)
  } catch {
    // 详情获取失败时保留列表行数据展示
  }
}

function handleTabChange(key: string | number) {
  if (key === 'logs' && !logLoaded.value) {
    logLoaded.value = true
    loadLogs()
  }
}

onMounted(loadTasks)
</script>

<style scoped>
.ellipsis-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.exception-text {
  color: #ff4d4f;
}
.detail-json {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
}
</style>
