<template>
  <div class="notification-records-page">
    <a-card :bordered="false" class="page-card">
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">通知记录</h2>
          <span class="page-desc">查看所有通知的发送状态与详情</span>
        </div>
        <div class="header-right">
          <a-switch v-model:checked="autoRefresh" size="small" @change="toggleAutoRefresh" />
          <span class="refresh-hint">自动刷新</span>
          <a-button style="margin-left: 12px" @click="loadRecords">
            <template #icon><reload-outlined /></template>
            刷新
          </a-button>
        </div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <a-select
          v-model:value="filterEvent"
          placeholder="事件类型"
          style="width: 200px"
          allow-clear
        >
          <a-select-option v-for="e in eventTypes" :key="e.code" :value="e.code">
            {{ e.name }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="filterStatus"
          placeholder="发送状态"
          style="width: 140px"
          allow-clear
        >
          <a-select-option value="pending">发送中</a-select-option>
          <a-select-option value="success">成功</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
        <a-range-picker v-model:value="dateRange" />
        <a-space>
          <a-button type="primary" @click="onFilterChange">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'event_code'">
            <a-tag :color="eventColor(record.event_code)">{{ eventName(record.event_code) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'title'">
            <span class="record-title">{{ record.title }}</span>
          </template>
          <template v-else-if="column.key === 'channel_name'">
            {{ record.channel_name || '-' }}
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            <span v-if="record.retry_count > 0" class="retry-count">（重试{{ record.retry_count }}次）</span>
          </template>
          <template v-else-if="column.key === 'duration_ms'">
            {{ formatDuration(record.duration_ms) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
              <a-popconfirm
                v-if="record.status === 'failed'"
                title="确定重新发送该通知吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleRetry(record)"
              >
                <a-button type="link" size="small">重试</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="detailVisible"
      title="通知详情"
      width="720px"
      :footer="null"
    >
      <a-descriptions :column="2" bordered size="small" v-if="currentRecord">
        <a-descriptions-item label="通知标题" :span="2">{{ currentRecord.title }}</a-descriptions-item>
        <a-descriptions-item label="事件类型">
          <a-tag :color="eventColor(currentRecord.event_code)">{{ eventName(currentRecord.event_code) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="发送状态">
          <a-tag :color="statusColor(currentRecord.status)">{{ statusLabel(currentRecord.status) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="通知渠道">{{ currentRecord.channel_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="重试次数">{{ currentRecord.retry_count }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ formatTime(currentRecord.created_at) }}</a-descriptions-item>
        <a-descriptions-item label="发送时间">{{ formatTime(currentRecord.sent_at) }}</a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.response_code" label="HTTP响应码">
          {{ currentRecord.response_code }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.duration_ms != null" label="耗时">
          {{ formatDuration(currentRecord.duration_ms) }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.error_message" label="错误信息" :span="2">
          <span class="error-text">{{ currentRecord.error_message }}</span>
        </a-descriptions-item>
      </a-descriptions>

      <div v-if="currentRecord" class="detail-section">
        <div class="section-title">卡片内容（JSON）</div>
        <pre class="json-block">{{ formatJson(currentRecord.content) }}</pre>
      </div>
      <div v-if="currentRecord?.response_body" class="detail-section">
        <div class="section-title">响应内容</div>
        <pre class="json-block">{{ formatJson(currentRecord.response_body) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import { notificationApi, type NotificationRecord, type EventTypeInfo } from '@/api/notifications'
const loading = ref(false)
const records = ref<NotificationRecord[]>([])
const eventTypes = ref<EventTypeInfo[]>([])
const filterEvent = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const dateRange = ref<[Dayjs, Dayjs] | undefined>(undefined)
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const detailVisible = ref(false)
const currentRecord = ref<NotificationRecord | null>(null)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

const columns = [
  { title: '时间', key: 'created_at', dataIndex: 'created_at', width: 170 },
  { title: '事件类型', key: 'event_code', dataIndex: 'event_code', width: 170 },
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true },
  { title: '渠道', key: 'channel_name', dataIndex: 'channel_name', width: 140 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 130 },
  { title: '耗时', key: 'duration_ms', dataIndex: 'duration_ms', width: 100 },
  { title: '操作', key: 'action', width: 130 },
]

function eventName(code: string): string {
  return eventTypes.value.find((e) => e.code === code)?.name || code
}

function eventColor(code: string): string {
  return eventTypes.value.find((e) => e.code === code)?.color || 'blue'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { pending: '发送中', success: '成功', failed: '失败' }
  return map[status] || status
}

function statusColor(status: string): string {
  const map: Record<string, string> = { pending: 'blue', success: 'green', failed: 'red' }
  return map[status] || 'default'
}

function formatTime(t?: string): string {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

function formatDuration(ms?: number): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatJson(text?: string): string {
  if (!text) return '-'
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filterEvent.value) params.event_code = filterEvent.value
    if (filterStatus.value) params.status = filterStatus.value
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0].format('YYYY-MM-DD')
      params.end_date = dateRange.value[1].format('YYYY-MM-DD')
    }
    const res = await notificationApi.getRecords(params)
    records.value = res.items
    pagination.total = res.total
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  try {
    eventTypes.value = await notificationApi.getEvents()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function onFilterChange() {
  pagination.current = 1
  loadRecords()
}

function handleReset() {
  filterEvent.value = undefined
  filterStatus.value = undefined
  dateRange.value = undefined
  pagination.current = 1
  loadRecords()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadRecords()
}

async function openDetail(record: NotificationRecord) {
  try {
    currentRecord.value = await notificationApi.getRecord(record.id)
    detailVisible.value = true
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleRetry(record: NotificationRecord) {
  try {
    await notificationApi.retryRecord(record.id)
    message.success('已重新发送')
    loadRecords()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function toggleAutoRefresh(checked: boolean) {
  if (checked) {
    refreshTimer = setInterval(() => {
      loadRecords()
    }, 10000)
  } else if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(() => {
  const params = { event: undefined, status: undefined, start_date: undefined, end_date: undefined }
  filterEvent.value = params.event
  filterStatus.value = params.status
  if (params.start_date && params.end_date) {
    dateRange.value = [dayjs(params.start_date), dayjs(params.end_date)]
  }
  loadEvents()
  loadRecords()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.notification-records-page {
  padding: 0;
}
.page-card {
  min-height: calc(100vh - 120px);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}
.page-desc {
  font-size: 13px;
  color: #8c8c8c;
  margin-left: 12px;
}
.header-left {
  display: flex;
  align-items: baseline;
}
.header-right {
  display: flex;
  align-items: center;
}
.refresh-hint {
  margin-left: 8px;
  font-size: 13px;
  color: #8c8c8c;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.record-title {
  color: #1f1f1f;
}
.retry-count {
  font-size: 12px;
  color: #fa8c16;
  margin-left: 4px;
}
.error-text {
  color: #ff4d4f;
  word-break: break-all;
}
.detail-section {
  margin-top: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 8px;
}
.json-block {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  color: #595959;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
