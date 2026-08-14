<template>
  <div class="task-monitor-page">
    <!-- 顶部统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :xs="12" :sm="12" :md="6">
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
      <a-col :xs="12" :sm="12" :md="6">
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
      <a-col :xs="12" :sm="12" :md="6">
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
      <a-col :xs="12" :sm="12" :md="6">
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
              <a-select-option value="STARTED">执行中</a-select-option>
              <a-select-option value="SUCCESS">成功</a-select-option>
              <a-select-option value="FAILURE">失败</a-select-option>
              <a-select-option value="PENDING">等待中</a-select-option>
              <a-select-option value="RETRY">重试中</a-select-option>
              <a-select-option value="REVOKED">已取消</a-select-option>
            </a-select>
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
        row-key="uuid"
        @expand="onExpand"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'state'">
            <a-tag :color="getStatusColor(record.state)">
              <a-badge :status="getBadgeStatus(record.state)" />
              {{ getStatusText(record.state) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'name'">
            <a-typography-text code copyable>{{ record.name }}</a-typography-text>
          </template>
          <template v-else-if="column.key === 'runtime'">
            <span v-if="record.runtime" class="runtime-text">
              {{ formatDuration(record.runtime) }}
            </span>
            <span v-else-if="record.state === 'STARTED'" class="running-text">
              <a-spin size="small" /> 执行中...
            </span>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'received'">
            {{ formatTime(record.received) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="showTaskDetail(record)">
              详情
            </a-button>
          </template>
        </template>
        <template #expandedRowRender="{ record }">
          <a-descriptions size="small" :column="2" bordered>
            <a-descriptions-item label="任务 UUID" :span="2">
              <a-typography-text code copyable style="font-size: 12px">{{ record.uuid }}</a-typography-text>
            </a-descriptions-item>
            <a-descriptions-item label="Worker">{{ record.worker || '-' }}</a-descriptions-item>
            <a-descriptions-item label="重试次数">{{ record.retries || 0 }}</a-descriptions-item>
            <a-descriptions-item label="开始时间" v-if="record.started">
              {{ formatTime(record.started) }}
            </a-descriptions-item>
            <a-descriptions-item label="完成时间" v-if="record.succeeded || record.failed">
              {{ formatTime(record.succeeded || record.failed) }}
            </a-descriptions-item>
            <a-descriptions-item label="参数" :span="2" v-if="record.args && record.args !== '()'">
              <a-typography-paragraph style="margin: 0; font-size: 12px" :ellipsis="{ rows: 2, expandable: true }">
                {{ record.args }}
              </a-typography-paragraph>
            </a-descriptions-item>
            <a-descriptions-item label="异常信息" :span="2" v-if="record.exception">
              <a-alert
                :message="record.exception"
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
        <a-descriptions-item label="任务名称">
          <a-tag color="blue">{{ selectedTask.name }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(selectedTask.state)">
            {{ getStatusText(selectedTask.state) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="UUID">
          <a-typography-text code copyable style="font-size: 12px">{{ selectedTask.uuid }}</a-typography-text>
        </a-descriptions-item>
        <a-descriptions-item label="Worker">{{ selectedTask.worker || '-' }}</a-descriptions-item>
        <a-descriptions-item label="运行时长">
          {{ selectedTask.runtime ? formatDuration(selectedTask.runtime) : '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="接收时间">
          {{ formatTime(selectedTask.received) }}
        </a-descriptions-item>
        <a-descriptions-item label="开始时间" v-if="selectedTask.started">
          {{ formatTime(selectedTask.started) }}
        </a-descriptions-item>
        <a-descriptions-item label="完成时间" v-if="selectedTask.succeeded || selectedTask.failed">
          {{ formatTime(selectedTask.succeeded || selectedTask.failed) }}
        </a-descriptions-item>
        <a-descriptions-item label="重试次数">{{ selectedTask.retries || 0 }}</a-descriptions-item>
        <a-descriptions-item label="参数" v-if="selectedTask.args && selectedTask.args !== '()'">
          <pre class="detail-pre">{{ selectedTask.args }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="关键字参数" v-if="selectedTask.kwargs && selectedTask.kwargs !== '{}'">
          <pre class="detail-pre">{{ selectedTask.kwargs }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="返回结果" v-if="selectedTask.result">
          <pre class="detail-pre">{{ selectedTask.result }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="异常信息" v-if="selectedTask.exception">
          <a-alert :message="selectedTask.exception" type="error" show-icon />
        </a-descriptions-item>
        <a-descriptions-item label="Traceback" v-if="selectedTask.traceback">
          <pre class="detail-pre traceback-pre">{{ selectedTask.traceback }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClusterOutlined,
  UnorderedListOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'

// Flower API 基础路径（通过 Vite 代理）
const FLOWER_API = '/flower/api'

const loading = ref(false)
const flowerOnline = ref(false)
const autoRefresh = ref(true)
const statusFilter = ref<string | undefined>(undefined)
const detailVisible = ref(false)
const selectedTask = ref<any>(null)

const workers = ref<Record<string, any>>({})
const tasks = ref<Record<string, any>>({})

let refreshTimer: number | null = null

// Worker 表格列
const workerColumns = [
  { title: 'Worker 名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '活跃任务', dataIndex: 'active', key: 'active', width: 100 },
  { title: '已处理', dataIndex: 'processed', key: 'processed', width: 100 },
  { title: '负载', key: 'load', width: 140 },
  { title: '进程 PID', dataIndex: 'pid', key: 'pid', width: 100 }
]

// 任务表格列
const taskColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '状态', dataIndex: 'state', key: 'state', width: 110 },
  { title: 'Worker', dataIndex: 'worker', key: 'worker', width: 220, ellipsis: true },
  { title: '运行时长', dataIndex: 'runtime', key: 'runtime', width: 120 },
  { title: '接收时间', dataIndex: 'received', key: 'received', width: 180 },
  { title: '操作', key: 'action', width: 80 }
]

// Worker 列表
const workerList = computed(() => {
  return Object.entries(workers.value).map(([name, info]: [string, any]) => ({
    name,
    status: info.status || 'online',
    active: (info.active || []).length,
    processed: info.tasks_total || info.processed || 0,
    concurrency: info.concurrency || info.pool?.max_concurrency || 4,
    pid: info.pid || info.stats?.pid || '-'
  }))
})

// 任务列表（按接收时间倒序）
const taskList = computed(() => {
  return Object.entries(tasks.value)
    .map(([uuid, task]: [string, any]) => ({
      uuid,
      ...task
    }))
    .sort((a: any, b: any) => (b.received || 0) - (a.received || 0))
})

// 按状态筛选
const filteredTasks = computed(() => {
  if (!statusFilter.value) return taskList.value
  return taskList.value.filter((t: any) => t.state === statusFilter.value)
})

// 统计数据
const stats = computed(() => {
  const taskArr = taskList.value
  return {
    workers: workerList.value.length,
    active: taskArr.filter((t: any) => t.state === 'STARTED').length,
    succeeded: taskArr.filter((t: any) => t.state === 'SUCCESS').length,
    failed: taskArr.filter((t: any) => t.state === 'FAILURE').length
  }
})

// 获取 Workers
async function fetchWorkers() {
  try {
    const resp = await fetch(`${FLOWER_API}/workers`, { method: 'GET' })
    if (resp.ok) {
      workers.value = await resp.json()
      flowerOnline.value = true
    } else {
      flowerOnline.value = false
    }
  } catch (e) {
    flowerOnline.value = false
  }
}

// 获取任务列表
async function fetchTasks() {
  try {
    const resp = await fetch(`${FLOWER_API}/tasks?limit=100`, { method: 'GET' })
    if (resp.ok) {
      tasks.value = await resp.json()
      flowerOnline.value = true
    }
  } catch (e) {
    // 忽略错误
  }
}

// 获取所有数据
async function fetchAll() {
  loading.value = true
  await Promise.all([fetchWorkers(), fetchTasks()])
  loading.value = false
}

// 展开行时获取任务详情
async function onExpand(expanded: boolean, record: any) {
  if (expanded && (!record.result || !record.exception)) {
    try {
      const resp = await fetch(`${FLOWER_API}/task/result/${record.uuid}`, { method: 'GET' })
      if (resp.ok) {
        const detail = await resp.json()
        tasks.value[record.uuid] = { ...tasks.value[record.uuid], ...detail }
      }
    } catch (e) {
      // 忽略
    }
  }
}

// 显示任务详情
async function showTaskDetail(record: any) {
  selectedTask.value = record
  detailVisible.value = true
  try {
    const resp = await fetch(`${FLOWER_API}/task/result/${record.uuid}`, { method: 'GET' })
    if (resp.ok) {
      const detail = await resp.json()
      selectedTask.value = { ...record, ...detail }
    }
  } catch (e) {
    // 忽略
  }
}

// 状态颜色
function getStatusColor(state: string): string {
  const colorMap: Record<string, string> = {
    STARTED: 'processing',
    SUCCESS: 'success',
    FAILURE: 'error',
    PENDING: 'warning',
    RETRY: 'warning',
    REVOKED: 'default'
  }
  return colorMap[state] || 'default'
}

// Badge 状态
function getBadgeStatus(state: string): 'success' | 'processing' | 'error' | 'default' | 'warning' {
  const statusMap: Record<string, 'success' | 'processing' | 'error' | 'default' | 'warning'> = {
    STARTED: 'processing',
    SUCCESS: 'success',
    FAILURE: 'error',
    PENDING: 'warning',
    RETRY: 'warning',
    REVOKED: 'default'
  }
  return statusMap[state] || 'default'
}

// 状态文本
function getStatusText(state: string): string {
  const textMap: Record<string, string> = {
    STARTED: '执行中',
    SUCCESS: '成功',
    FAILURE: '失败',
    PENDING: '等待中',
    RETRY: '重试中',
    REVOKED: '已取消'
  }
  return textMap[state] || state
}

// 格式化时长
function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

// 格式化时间戳
function formatTime(timestamp: number): string {
  if (!timestamp) return '-'
  const date = new Date(timestamp * 1000)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(() => {
  fetchAll()
  refreshTimer = window.setInterval(() => {
    if (autoRefresh.value) {
      fetchAll()
    }
  }, 5000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
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
