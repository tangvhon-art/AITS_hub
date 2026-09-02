<template>
  <div class="task-monitor-page">
    <!-- 顶部统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :xs="12" :sm="12" :md="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="Worker 进程"
            :value="stats.workers"
            :value-style="{ color: '#1677ff' }"
          >
            <template #prefix>
              <DatabaseOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="5">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="执行中"
            :value="stats.active"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix>
              <PlayCircleOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="5">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="排队中"
            :value="stats.queued"
            :value-style="{ color: '#faad14' }"
          >
            <template #prefix>
              <HourglassOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="5">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="已完成"
            :value="stats.succeeded"
            :value-style="{ color: '#722ed1' }"
          >
            <template #prefix>
              <CheckCircleOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="5">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="失败"
            :value="stats.failed"
            :value-style="{ color: '#ff4d4f' }"
          >
            <template #prefix>
              <CloseCircleOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- Worker 列表 -->
    <a-card class="section-card" :bordered="false">
      <template #title>
        <div class="card-title">
          <ClusterOutlined />
          <span>Worker 节点</span>
        </div>
      </template>
      <template #extra>
        <div class="card-extra">
          <a-tag :color="flowerOnline ? 'green' : 'red'">
            <a-badge :status="flowerOnline ? 'success' : 'error'" />
            {{ flowerOnline ? 'Flower 在线' : 'Flower 离线' }}
          </a-tag>
        </div>
      </template>
      <a-table
        :columns="workerColumns"
        :data-source="workerList"
        :loading="loading"
        :pagination="false"
        size="middle"
        row-key="name"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-badge
              :status="record.status === 'online' ? 'success' : 'error'"
              :text="record.status === 'online' ? '在线' : '离线'"
            />
          </template>
          <template v-else-if="column.key === 'active'">
            <a-tag color="blue">{{ record.active }}</a-tag>
          </template>
          <template v-else-if="column.key === 'queued'">
            <a-tag :color="record.queued > 0 ? 'orange' : 'default'">{{ record.queued }}</a-tag>
          </template>
          <template v-else-if="column.key === 'processed'">
            <a-tag color="purple">{{ record.processed }}</a-tag>
          </template>
          <template v-else-if="column.key === 'load'">
            <a-progress
              :percent="Math.min(100, Math.round((record.active / Math.max(1, record.concurrency)) * 100))"
              size="small"
              :show-info="false"
              :stroke-color="record.active > 0 ? '#1677ff' : '#d9d9d9'"
              style="width: 80px"
            />
            <span class="load-text">{{ record.active }}/{{ record.concurrency }}</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 任务列表 -->
    <a-card class="section-card" :bordered="false">
      <template #title>
        <div class="card-title">
          <UnorderedListOutlined />
          <span>任务列表</span>
        </div>
      </template>
      <template #extra>
        <div class="card-extra">
            <a-select
              v-model:value="statusFilter"
              style="width: 130px"
              placeholder="状态筛选"
              allow-clear
              size="small"
            >
              <a-select-option value="running">执行中</a-select-option>
              <a-select-option value="pending">排队中</a-select-option>
              <a-select-option value="success">成功</a-select-option>
              <a-select-option value="failed">失败</a-select-option>
              <a-select-option value="canceled">已取消</a-select-option>
            </a-select>
            <a-button size="small" type="primary" @click="handleSearch" style="margin-left: 8px">查询</a-button>
            <a-button size="small" @click="handleReset">重置</a-button>
            <a-tooltip title="自动刷新">
              <a-switch
                v-model:checked="autoRefresh"
                checked-children="自动"
                un-checked-children="手动"
                size="small"
                style="margin-left: 8px"
              />
            </a-tooltip>
            <a-button size="small" @click="fetchAll" :loading="loading" style="margin-left: 8px">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
        </div>
      </template>
      <a-table
        :columns="taskColumns"
        :data-source="filteredTasks"
        :loading="loading"
        :pagination="{ pageSize: 10, showSizeChanger: true, showTotal: (total: number) => `共 ${total} 条` }"
        size="middle"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'state'">
            <a-tag :color="getStatusColor(record.status)">
              <a-badge :status="getBadgeStatus(record.status)" />
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'name'">
            <a-tag color="blue">{{ agentTypeText(record.agent_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'backend'">
            <a-tag :color="backendColor(record.backend)">{{ backendText(record.backend) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'completed_at'">
            {{ record.completed_at ? formatTime(record.completed_at) : '-' }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="showTaskDetail(record)">
              详情
            </a-button>
            <a-popconfirm
              v-if="['running', 'pending'].includes(record.status)"
              title="确定取消该任务吗？"
              ok-text="取消任务"
              cancel-text="再想想"
              @confirm="handleCancel(record)"
            >
              <a-button type="link" danger size="small">取消</a-button>
            </a-popconfirm>
          </template>
        </template>
        <template #expandedRowRender="{ record }">
          <a-descriptions size="small" :column="2" bordered>
            <a-descriptions-item label="任务 ID">{{ record.id }}</a-descriptions-item>
            <a-descriptions-item label="项目 ID">{{ record.project_id || '-' }}</a-descriptions-item>
            <a-descriptions-item label="执行后端">{{ backendText(record.backend) }}</a-descriptions-item>
            <a-descriptions-item label="LLM 配置">{{ record.llm_config_id || '-' }}</a-descriptions-item>
            <a-descriptions-item label="输入参数" :span="2">
              <pre class="detail-pre">{{ JSON.stringify(record.input_params, null, 2) }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="输出结果" :span="2" v-if="record.output_result && Object.keys(record.output_result).length">
              <pre class="detail-pre">{{ JSON.stringify(record.output_result, null, 2) }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="错误信息" :span="2" v-if="record.error_message">
              <a-alert
                :message="record.error_message"
                type="error"
                show-icon
                style="font-size: 12px"
              />
            </a-descriptions-item>
          </a-descriptions>
        </template>
      </a-table>
    </a-card>

    <!-- 任务详情抽屉 -->
    <a-drawer
      v-model:open="detailVisible"
      title="任务详情"
      placement="right"
      width="560"
    >
      <a-descriptions v-if="selectedTask" :column="1" bordered size="small">
        <a-descriptions-item label="任务 ID">
          <a-tag color="blue">{{ selectedTask.id }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="Agent 类型">
          <a-tag color="blue">{{ agentTypeText(selectedTask.agent_type) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(selectedTask.status)">
            {{ getStatusText(selectedTask.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行后端">{{ backendText(selectedTask.backend) }}</a-descriptions-item>
        <a-descriptions-item label="项目 ID">{{ selectedTask.project_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="LLM 配置">{{ selectedTask.llm_config_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">
          {{ formatTime(selectedTask.created_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="完成时间">
          {{ selectedTask.completed_at ? formatTime(selectedTask.completed_at) : '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="输入参数">
          <pre class="detail-pre">{{ JSON.stringify(selectedTask.input_params, null, 2) }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="输出结果" v-if="selectedTask.output_result && Object.keys(selectedTask.output_result).length">
          <pre class="detail-pre">{{ JSON.stringify(selectedTask.output_result, null, 2) }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="Token 消耗" v-if="selectedTask.token_usage">
          <pre class="detail-pre">{{ JSON.stringify(selectedTask.token_usage, null, 2) }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="异常信息" v-if="selectedTask.error_message">
          <a-alert :message="selectedTask.error_message" type="error" show-icon />
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClusterOutlined,
  UnorderedListOutlined,
  ReloadOutlined,
  HourglassOutlined
} from '@ant-design/icons-vue'
import { getAgentTaskMonitor, cancelAgentTask, type AgentTaskMonitor, type AgentTask } from '@/api/agentTasks'
import { AI_BACKEND_TEXT, AI_BACKEND_COLOR } from '@/constants/enums'

// Flower API 基础路径（通过 Vite 代理，仅用于 Worker 节点在线状态展示）
const FLOWER_API = '/flower/api'

const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const flowerOnline = ref(false)
const autoRefresh = ref(true)
const statusFilter = ref<string | undefined>(undefined)
const detailVisible = ref(false)
const selectedTask = ref<AgentTask | null>(null)

const monitor = ref<AgentTaskMonitor>({
  running: 0, pending: 0, success: 0, failed: 0, canceled: 0,
  queues: {}, queue_stats: {}, workers: {}, recent: [],
})

let refreshTimer: number | null = null

// Agent 类型中文
const AGENT_TYPE_TEXT: Record<string, string> = {
  case_generator: '用例生成', case_reviewer: '用例评审', case_optimizer: '用例优化',
  requirement_generator: '需求生成', api_case_generator: '接口用例生成', api_doc_generator: '接口文档生成',
  ui_execution: 'UI执行', defect_analyzer: '缺陷分析', report_generator: '报告生成',
  bdd_generator: 'BDD生成', script_generator: '脚本生成', script_fixer: '脚本修复',
  knowledge_processor: '知识库处理', supervisor: 'Supervisor', notification: '通知',
}
const agentTypeText = (t: string) => AGENT_TYPE_TEXT[t] || t || '-'
const backendText = (b?: string | null) => b ? (AI_BACKEND_TEXT as any)[b] || b : '本地'
const backendColor = (b?: string | null) => b ? (AI_BACKEND_COLOR as any)[b] || 'default' : 'green'

// Worker 表格列
const workerColumns = [
  { title: 'Worker 名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '队列', dataIndex: 'queue', key: 'queue', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '活跃任务', dataIndex: 'active', key: 'active', width: 110 },
  { title: '排队中', dataIndex: 'queued', key: 'queued', width: 100 },
  { title: '已处理', dataIndex: 'processed', key: 'processed', width: 100 },
  { title: '负载', key: 'load', width: 140 },
  { title: '进程 PID', dataIndex: 'pid', key: 'pid', width: 100 }
]

// 任务表格列
const taskColumns = [
  { title: '任务名称', dataIndex: 'agent_type', key: 'name', width: 160 },
  { title: '状态', dataIndex: 'status', key: 'state', width: 100 },
  { title: '执行后端', dataIndex: 'backend', key: 'backend', width: 110 },
  { title: '项目', dataIndex: 'project_id', key: 'project', width: 70 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '完成时间', dataIndex: 'completed_at', key: 'completed_at', width: 180 },
  { title: '操作', key: 'action', width: 80 }
]

// Worker -> 队列映射（与 celery_app.py 队列划分对齐）
const WORKER_QUEUE: Record<string, string> = {
  'ai-worker': 'ai',
  'eval-worker': 'eval',
  'execution-worker': 'execution',
  'default-worker': 'default'
}

// Worker 列表（在线状态来自后端 control inspect 探测，活跃/排队/已处理来自后端按队列聚合的 DB+Redis 权威统计）
const workerList = computed(() => {
  const qs = monitor.value.queue_stats || {}
  const wd = monitor.value.workers || {}
  return Object.entries(wd).map(([name, info]: [string, any]) => {
    const queue = (info.queue && info.queue[0]) || WORKER_QUEUE[name.split('@')[0]] || 'default'
    const q = qs[queue] || { queued: 0, active: 0, processed: 0 }
    return {
      name,
      queue,
      status: 'online',
      active: q.active,
      queued: q.queued,
      processed: q.processed,
      concurrency: info.concurrency || 1,
      pid: info.pid || '-'
    }
  })
})

// 任务列表（AgentTask，按创建时间倒序，来自 DB 权威状态）
const taskList = computed(() => monitor.value.recent || [])
const filteredTasks = computed(() => {
  if (!statusFilter.value) return taskList.value
  return taskList.value.filter((t: any) => t.status === statusFilter.value)
})

function handleSearch() {
  syncToUrl({ status: statusFilter.value })
}
function handleReset() {
  statusFilter.value = undefined
  syncToUrl({ status: statusFilter.value })
}

// 统计数据（执行中/排队中以 DB agent_tasks + Redis 队列积压为准，不依赖 Celery 事件流）
const stats = computed(() => {
  const queueTotal = Object.values(monitor.value.queues || {}).reduce((a, b) => a + b, 0)
  return {
    workers: workerList.value.length,
    active: monitor.value.running,
    queued: monitor.value.pending + queueTotal,
    succeeded: monitor.value.success,
    failed: monitor.value.failed,
  }
})

// 获取 Agent 任务监控汇总（DB 权威状态）
async function fetchMonitor() {
  try {
    monitor.value = await getAgentTaskMonitor()
  } catch (e) {
    // 忽略
  }
}

// 获取 Workers（仅检查 Flower 是否在线；Worker 列表已改由后端 monitor.workers 提供）
async function fetchWorkers() {
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 3000)
    const resp = await fetch(`${FLOWER_API}/workers`, { method: 'GET', signal: ctrl.signal })
    clearTimeout(timer)
    if (resp.ok) {
      flowerOnline.value = true
    } else {
      flowerOnline.value = false
    }
  } catch (e) {
    flowerOnline.value = false
  }
}

// 获取所有数据
async function fetchAll() {
  loading.value = true
  await Promise.all([fetchMonitor(), fetchWorkers()])
  loading.value = false
}

// 显示任务详情
function showTaskDetail(record: AgentTask) {
  selectedTask.value = record
  detailVisible.value = true
}

// 手动取消任务
async function handleCancel(record: AgentTask) {
  try {
    await cancelAgentTask(record.id)
    message.success(`任务 ${record.id} 已取消`)
    await fetchAll()
  } catch (e: any) {
    message.error(e?.message || '取消任务失败')
  }
}

// 状态颜色
function getStatusColor(state: string): string {
  const colorMap: Record<string, string> = {
    running: 'processing',
    success: 'success',
    failed: 'error',
    pending: 'warning',
    canceled: 'default',
    ready: 'blue'
  }
  return colorMap[state] || 'default'
}

// Badge 状态
function getBadgeStatus(state: string): 'success' | 'processing' | 'error' | 'default' | 'warning' {
  const statusMap: Record<string, 'success' | 'processing' | 'error' | 'default' | 'warning'> = {
    running: 'processing',
    success: 'success',
    failed: 'error',
    pending: 'warning',
    canceled: 'default',
    ready: 'default'
  }
  return statusMap[state] || 'default'
}

// 状态文本
function getStatusText(state: string): string {
  const textMap: Record<string, string> = {
    running: '执行中',
    success: '成功',
    failed: '失败',
    pending: '排队中',
    canceled: '已取消',
    ready: '就绪'
  }
  return textMap[state] || state
}

// 格式化时间
function formatTime(timestamp?: string | null): string {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(() => {
  const params = loadFromUrl({ status: undefined })
  statusFilter.value = params.status
  fetchAll()
  refreshTimer = window.setInterval(() => {
    if (autoRefresh.value) {
      fetchAll()
    }
  }, 5000)
})

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.task-monitor-page {
  padding: 0;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.section-card {
  margin-bottom: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.card-extra {
  display: flex;
  align-items: center;
}

.load-text {
  margin-left: 8px;
  font-size: 12px;
  color: #8c8c8c;
}

.runtime-text {
  font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace;
  font-size: 13px;
  color: #262626;
}

.running-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #1677ff;
  font-size: 13px;
}

.detail-pre {
  margin: 0;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.traceback-pre {
  color: #ff4d4f;
  background: #fff2f0;
}
</style>
