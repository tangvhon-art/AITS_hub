<template>
  <div class="api-cases">
    <PageHeader title="测试用例">
  <template #extra>
    <a-button @click="showAiModal = true">
          <template #icon><RobotOutlined /></template>
          AI 生成用例
        </a-button>
        <a-button type="primary" @click="handleCreate">
          <template #icon><PlusOutlined /></template>
          新建用例
        </a-button>
  </template>
</PageHeader><a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
  <a-form layout="inline">
    <a-form-item label="用例名称">
<a-input-search v-model:value="keyword" placeholder="搜索用例名称" style="width: 250px" @search="loadData" />
</a-form-item>
        <a-form-item label="优先级">
<a-select v-model:value="priorityFilter" placeholder="优先级" style="width: 100px" allow-clear>
          <a-select-option value="P0">P0</a-select-option>
          <a-select-option value="P1">P1</a-select-option>
          <a-select-option value="P2">P2</a-select-option>
          <a-select-option value="P3">P3</a-select-option>
        </a-select>
</a-form-item>
  </a-form>
</SearchBar><DataTable
        :columns="columns"
        :data-source="dataSource"
        :loading="loading"
        @change="handleTableChange"
        row-key="id"
        :row-selection="rowSelection"
      >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
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
              <a-button type="link" size="small" danger @click="confirmDelete(record, () => handleDelete(record))">删除</a-button>
            </a-space>
          </template>
        </template>
      </DataTable>

      <div v-if="selectedRowKeys.length > 0" class="batch-actions">
        <span>已选 {{ selectedRowKeys.length }} 项</span>
        <a-form-item label="筛选">
<a-select
          v-model:value="selectedEnvId"
          placeholder="选择执行环境"
          style="width: 220px"
          allow-clear
        >
          <a-select-option
            v-for="env in runEnvironments"
            :key="env.id"
            :value="env.id"
          >
            {{ env.name }}{{ env.is_default ? '（默认）' : '' }}
          </a-select-option>
        </a-select>
</a-form-item>
        <a-button type="primary" size="small" :loading="batchRunLoading" @click="handleBatchRun">批量执行</a-button>
      </div>
    </a-card>

    <!-- AI生成弹窗 -->
    <AiGenerateCasesModal
      v-model:open="showAiModal"
      :project-id="projectId"
      @saved="loadData"
    />

    <!-- 执行环境选择弹窗 -->
    <FormModal
      v-model:visible="runModalVisible"
      title="选择执行环境"
      :loading="runLoading"
      width="600"
      @ok="confirmRun"
    >
      <div style="margin-bottom: 12px">
        用例：<strong>{{ runningCase?.name }}</strong>
      </div>
      <a-select
        v-model:value="selectedEnvId"
        placeholder="请选择环境（提供 base_url 和环境变量）"
        style="width: 100%"
        :options="runEnvironments.map(e => ({ label: `${e.name}${e.is_default ? '（默认）' : ''} - ${e.base_url}`, value: e.id }))"
      />
      <div v-if="runEnvironments.length === 0" style="color: #999; margin-top: 8px">
        暂无环境，请先在「环境变量」中创建
      </div>
    </FormModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { apiCasesApi, type ApiTestCase } from '@/api/apiTest'
import { environmentsApi, type TestEnvironment } from '@/api/environments'
import AiGenerateCasesModal from './AiGenerateCasesModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useConfirmDelete } from '@/composables/useConfirmDelete'
const { confirmDelete } = useConfirmDelete('接口用例')
const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const loading = ref(false)
const keyword = ref('')
const priorityFilter = ref<string | undefined>(undefined)
const dataSource = ref<ApiTestCase[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const showAiModal = ref(false)

// 执行环境选择弹窗
const runModalVisible = ref(false)
const runLoading = ref(false)
const runEnvironments = ref<TestEnvironment[]>([])
const selectedEnvId = ref<number | null>(null)
const runningCase = ref<ApiTestCase | null>(null)

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

function handleReset() {
  keyword.value = ''
  priorityFilter.value = undefined
  pagination.value.current = 1
  loadData()
}
function handleSearch() {
  pagination.value.current = 1
  loadData()
}


const handleCreate = () => {
  router.push(`/projects/${projectId}/api-test/cases/new`)
}

const handleEdit = (record: ApiTestCase) => {
  router.push(`/projects/${projectId}/api-test/cases/${record.id}`)
}

const handleRun = async (record: ApiTestCase) => {
  runningCase.value = record
  selectedEnvId.value = null
  runModalVisible.value = true
  // 加载环境列表
  try {
    runEnvironments.value = await environmentsApi.list(projectId)
    // 默认选中第一个或默认环境
    const defaultEnv = runEnvironments.value.find(e => e.is_default) || runEnvironments.value[0]
    if (defaultEnv) selectedEnvId.value = defaultEnv.id
  } catch {
    runEnvironments.value = []
  }
}

const confirmRun = async () => {
  if (!runningCase.value) return
  const env = runEnvironments.value.find(e => e.id === selectedEnvId.value)
  const runData: any = {}
  if (env) {
    runData.base_url = env.base_url
    runData.environment_id = env.id
  }
  runLoading.value = true
  try {
    const res = await apiCasesApi.run(projectId, runningCase.value.id, runData)
    message.success(`执行完成: ${res.status}`)
    runModalVisible.value = false
    if (res.execution_id) {
      router.push(`/projects/${projectId}/api-test/executions/${res.execution_id}`)
    }
  } finally {
    runLoading.value = false
  }
}

const batchRunLoading = ref(false)

const handleBatchRun = async () => {
  batchRunLoading.value = true
  try {
    const res = await apiCasesApi.batchRun(projectId, selectedRowKeys.value, selectedEnvId.value || undefined)
    const passed = res.passed || 0
    const failed = res.failed || 0
    const total = res.total || 0
    if (failed > 0) {
      message.warning(`批量执行完成：${total} 个用例，通过 ${passed} 个，失败 ${failed} 个`)
    } else {
      message.success(`批量执行完成：${total} 个用例全部通过`)
    }
    selectedRowKeys.value = []
    loadData()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '批量执行失败')
  } finally {
    batchRunLoading.value = false
  }
}

const handleDelete = async (record: ApiTestCase) => {
  await apiCasesApi.delete(projectId, record.id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  const params = { keyword: '', priority: undefined }
  keyword.value = params.keyword
  priorityFilter.value = params.priority || undefined
  loadData()
})
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
