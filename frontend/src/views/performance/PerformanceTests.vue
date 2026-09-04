<template>
  <div class="performance-tests">
    <PageHeader title="性能测试">
  <template #extra>
    <a-button type="primary" @click="handleCreate">
          <template #icon><PlusOutlined /></template>
          新建测试
        </a-button>
  </template>
</PageHeader><a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
  <a-form layout="inline">
    <a-form-item label="测试名称">
<a-input-search v-model:value="keyword" placeholder="搜索测试名称" allow-clear style="width: 250px" @search="loadData" />
</a-form-item>
        <a-form-item label="状态">
<a-select v-model:value="statusFilter" allow-clear placeholder="状态筛选" style="width: 150px">
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="running">运行中</a-select-option>
          <a-select-option value="completed">已执行</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
          <a-select-option value="stopped">已停止</a-select-option>
        </a-select>
</a-form-item>
  </a-form>
</SearchBar><DataTable :columns="columns" :data-source="dataSource" :loading="loading" row-key="id" @change="handleTableChange">
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-if="column.key === 'target_type'">
            <a-tag>{{ targetTypeText(record.target_type) }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button size="small" type="link" :disabled="record.status === 'running'" @click="handleRun(record)">执行</a-button>
              <a-button size="small" type="link" @click="handleEdit(record)">编辑</a-button>
              <a-button size="small" type="link" @click="handleViewRuns(record)">记录</a-button>
              <a-button size="small" type="link" danger @click="confirmDelete(record, () => handleDelete(record))">删除</a-button>
            </a-space>
          </template>
        </template>
      </DataTable>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { performanceTestsApi, type PerformanceTest } from '@/api/performanceTests'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import { useConfirmDelete } from '@/composables/useConfirmDelete'
const { confirmDelete } = useConfirmDelete('性能测试')
const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref<string | undefined>(undefined)
const dataSource = ref<PerformanceTest[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
let pollTimer: ReturnType<typeof setInterval> | null = null

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '目标类型', key: 'target_type', width: 120 },
  { title: '并发数', dataIndex: 'users', key: 'users', width: 80 },
  { title: 'Spawn Rate', dataIndex: 'spawn_rate', key: 'spawn_rate', width: 100 },
  { title: '持续时间(s)', dataIndex: 'duration', key: 'duration', width: 110 },
  { title: '状态', key: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' as const },
]

const statusColor = (s: string) => ({ draft: 'default', running: 'processing', completed: 'success', failed: 'error', stopped: 'warning' })[s] || 'default'
const statusText = (s: string) => ({ draft: '草稿', running: '运行中', completed: '已执行', failed: '失败', stopped: '已停止' })[s] || s
const targetTypeText = (t: string) => ({ api_definition: '接口定义', api_case: '接口用例', api_scenario: '接口场景' })[t] || t

async function loadData() {
  loading.value = true
  try {
    const res = await performanceTestsApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: keyword.value || undefined,
      status: statusFilter.value,
    })
    dataSource.value = res.items
    pagination.value.total = res.total
    startPollingIfNeeded()
  } catch { } finally {
    loading.value = false
  }
}

function startPollingIfNeeded() {
  stopPolling()
  const hasRunning = dataSource.value.some(t => t.status === 'running')
  if (hasRunning) {
    pollTimer = setInterval(async () => {
      try {
        const res = await performanceTestsApi.list(projectId, {
          page: pagination.value.current,
          page_size: pagination.value.pageSize,
          keyword: keyword.value || undefined,
          status: statusFilter.value,
        })
        dataSource.value = res.items
        pagination.value.total = res.total
        if (!res.items.some((t: PerformanceTest) => t.status === 'running')) {
          stopPolling()
        }
      } catch { }
    }, 5000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleTableChange(p: any) {
  pagination.value.current = p.current
  pagination.value.pageSize = p.pageSize
  loadData()
}

function handleReset() {
  keyword.value = ''
  statusFilter.value = undefined
  pagination.value.current = 1
  loadData()
}
function handleSearch() {
  pagination.value.current = 1
  loadData()
}


function handleCreate() {
  router.push(`/projects/${projectId}/performance-tests/new`)
}

function handleEdit(record: PerformanceTest) {
  router.push(`/projects/${projectId}/performance-tests/${record.id}`)
}

function handleViewRuns(record: PerformanceTest) {
  router.push(`/projects/${projectId}/performance-tests/${record.id}/runs`)
}

async function handleRun(record: PerformanceTest) {
  try {
    await performanceTestsApi.run(projectId, record.id)
    message.success('性能测试已启动')
    loadData()
  } catch { }
}

async function handleDelete(record: PerformanceTest) {
  try {
    await performanceTestsApi.delete(projectId, record.id)
    message.success('删除成功')
    loadData()
  } catch { }
}

onMounted(() => {
  const params = { keyword: '', status: undefined }
  keyword.value = params.keyword
  statusFilter.value = params.status
  loadData()
})
onUnmounted(() => stopPolling())
</script>

<style scoped>
.performance-tests { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>

<style>
.ant-popconfirm-buttons {
  display: flex !important;
  flex-direction: row !important;
  gap: 8px;
}
</style>
