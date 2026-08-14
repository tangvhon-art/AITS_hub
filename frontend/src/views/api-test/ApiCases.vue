<template>
  <div class="api-cases">
    <div class="page-header">
      <h2>测试用例</h2>
      <div class="header-actions">
        <a-button @click="showAiModal = true">
          <template #icon><RobotOutlined /></template>
          AI 生成用例
        </a-button>
        <a-button type="primary" @click="handleCreate">
          <template #icon><PlusOutlined /></template>
          新建用例
        </a-button>
      </div>
    </div>

    <a-card>
      <div class="filter-bar">
        <a-input-search v-model:value="keyword" placeholder="搜索用例名称" style="width: 250px" @search="loadData" />
        <a-select v-model:value="priorityFilter" placeholder="优先级" style="width: 100px" allow-clear @change="loadData">
          <a-select-option value="P0">P0</a-select-option>
          <a-select-option value="P1">P1</a-select-option>
          <a-select-option value="P2">P2</a-select-option>
          <a-select-option value="P3">P3</a-select-option>
        </a-select>
      </div>

      <a-table
        :columns="columns"
        :data-source="dataSource"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
        :row-selection="rowSelection"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="getMethodColor(record.method)">{{ record.method }}</a-tag>
          </template>
          <template v-else-if="column.key === 'priority'">
            <a-tag :color="getPriorityColor(record.priority)">{{ record.priority }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleRun(record)">执行</a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
              <a-popconfirm title="确定删除该用例？" @confirm="handleDelete(record)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>

      <div v-if="selectedRowKeys.length > 0" class="batch-actions">
        <span>已选 {{ selectedRowKeys.length }} 项</span>
        <a-button type="primary" size="small" @click="handleBatchRun">批量执行</a-button>
      </div>
    </a-card>

    <!-- AI生成弹窗 -->
    <AiGenerateCasesModal
      v-model:open="showAiModal"
      :project-id="projectId"
      @saved="loadData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { apiCasesApi, type ApiTestCase } from '@/api/apiTest'
import AiGenerateCasesModal from './AiGenerateCasesModal.vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const loading = ref(false)
const keyword = ref('')
const priorityFilter = ref('')
const dataSource = ref<ApiTestCase[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const showAiModal = ref(false)

const selectedRowKeys = ref<number[]>([])
const rowSelection = {
  selectedRowKeys,
  onChange: (keys: number[]) => { selectedRowKeys.value = keys }
}

const columns = [
  { title: '用例名称', dataIndex: 'name', key: 'name' },
  { title: '方法', key: 'method', width: 80 },
  { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
  { title: '优先级', key: 'priority', width: 80 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: 180 },
]

const getMethodColor = (method: string) => {
  const colors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }
  return colors[method] || 'default'
}

const getPriorityColor = (priority: string) => {
  const colors: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return colors[priority] || 'default'
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await apiCasesApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: keyword.value,
      priority: priorityFilter.value,
    })
    dataSource.value = res.items
    pagination.value.total = res.total
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag: any) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadData()
}

const handleCreate = () => {
  router.push(`/projects/${projectId}/api-cases/new`)
}

const handleEdit = (record: ApiTestCase) => {
  router.push(`/projects/${projectId}/api-cases/${record.id}`)
}

const handleRun = async (record: ApiTestCase) => {
  try {
    const res = await apiCasesApi.run(projectId, record.id, {})
    message.success(`执行完成: ${res.status}`)
    if (res.execution_id) {
      router.push(`/projects/${projectId}/api-executions/${res.execution_id}`)
    }
  } catch {}
}

const handleBatchRun = async () => {
  try {
    await apiCasesApi.batchRun(projectId, selectedRowKeys.value)
    message.success('批量执行已提交')
    selectedRowKeys.value = []
  } catch {}
}

const handleDelete = async (record: ApiTestCase) => {
  await apiCasesApi.delete(projectId, record.id)
  message.success('删除成功')
  loadData()
}

onMounted(() => loadData())
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.batch-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
