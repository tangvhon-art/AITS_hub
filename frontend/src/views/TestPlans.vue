<template>
  <div class="plans-page">
    <div class="page-header">
      <h2>测试计划管理</h2>
      <div>
        <a-button @click="showEnvModal = true" style="margin-right: 8px">
          <EnvironmentOutlined /> 环境管理
        </a-button>
        <a-button type="primary" @click="openCreateModal">
          <PlusOutlined /> 新建计划
        </a-button>
      </div>
    </div>

    <div class="filter-bar">
      <a-input v-model:value="filterName" placeholder="计划名称" allow-clear style="width: 180px" />
      <a-select v-model:value="filterVersionId" placeholder="所属版本" allow-clear style="width: 150px">
        <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
      </a-select>
      <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px">
        <a-select-option value="draft">草稿</a-select-option>
        <a-select-option value="scheduled">已排期</a-select-option>
        <a-select-option value="running">执行中</a-select-option>
        <a-select-option value="completed">已完成</a-select-option>
        <a-select-option value="failed">已失败</a-select-option>
        <a-select-option value="archived">已归档</a-select-option>
      </a-select>
      <a-select v-model:value="filterPriority" placeholder="优先级" allow-clear style="width: 120px">
        <a-select-option value="P0">P0</a-select-option>
        <a-select-option value="P1">P1</a-select-option>
        <a-select-option value="P2">P2</a-select-option>
        <a-select-option value="P3">P3</a-select-option>
      </a-select>
      <a-button type="primary" @click="loadPlans">查询</a-button>
      <a-button @click="handleReset">重置</a-button>
    </div>

    <a-card>
      <a-table
        :columns="columns"
        :data-source="plans"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'version'">
            <a-tag v-if="record.version_id" color="blue">{{ getVersionName(record.version_id) }}</a-tag>
            <span v-else style="color: #999">-</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">{{ getStatusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'priority'">
            <a-tag :color="getPriorityColor(record.priority)">{{ record.priority }}</a-tag>
          </template>
          <template v-else-if="column.key === 'last_pass_rate'">
            <a-progress :percent="record.last_pass_rate || 0" size="small" />
          </template>
          <template v-else-if="column.key === 'last_execution_id'">
            <a-tag v-if="record.last_execution_id" color="blue" style="cursor:pointer" @click="viewReport(record)">
              #{{ record.last_execution_id }}
            </a-tag>
            <span v-else style="color:#999">-</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="handleExecute(record)" :disabled="record.status === 'running'">执行</a-button>
            <a-button type="link" size="small" @click="editPlan(record)">编辑</a-button>
            <a-button type="link" size="small" @click="viewReport(record)" v-if="record.last_execution_id">报告</a-button>
            <a-popconfirm title="确定删除该计划？" @confirm="handleDelete(record)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建计划弹窗（仅基本信息，创建后跳转编排页） -->
    <a-modal
      v-model:open="showCreateModal"
      title="新建测试计划"
      width="600px"
      @ok="handleSubmit"
      :confirm-loading="submitting"
      @cancel="resetForm"
    >
      <a-form layout="vertical" :model="formData">
        <a-form-item label="计划名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入计划名称" />
        </a-form-item>
        <a-form-item label="计划描述">
          <a-textarea v-model:value="formData.description" :rows="3" placeholder="请输入计划描述" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="优先级">
              <a-select v-model:value="formData.priority">
                <a-select-option value="P0">P0 - 紧急</a-select-option>
                <a-select-option value="P1">P1 - 高</a-select-option>
                <a-select-option value="P2">P2 - 中</a-select-option>
                <a-select-option value="P3">P3 - 低</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所属版本">
              <a-select v-model:value="formData.version_id" allow-clear placeholder="选择版本（可选）">
                <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="测试环境">
          <a-select v-model:value="formData.environment_id" allow-clear placeholder="选择测试环境">
            <a-select-option v-for="env in environments" :key="env.id" :value="env.id">
              {{ env.name }} ({{ env.base_url }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="调度类型">
          <a-select v-model:value="formData.schedule_type">
            <a-select-option value="manual">手动执行</a-select-option>
            <a-select-option value="once">一次性执行</a-select-option>
            <a-select-option value="cron">定时执行</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 环境管理弹窗 -->
    <a-modal v-model:open="showEnvModal" title="测试环境管理" width="700px" :footer="null">
      <div style="margin-bottom: 12px">
        <a-button type="primary" size="small" @click="showEnvCreate = true">
          <PlusOutlined /> 新建环境
        </a-button>
      </div>
      <a-table :columns="envColumns" :data-source="environments" size="small" :pagination="false" row-key="id">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'is_default'">
            <a-tag v-if="record.is_default" color="blue">默认</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="editEnv(record)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="deleteEnv(record)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>

      <!-- 新建/编辑环境 -->
      <a-modal
        v-model:open="showEnvCreate"
        :title="editingEnv ? '编辑环境' : '新建环境'"
        width="500px"
        @ok="submitEnv"
        :confirm-loading="envSubmitting"
      >
        <a-form layout="vertical" :model="envForm">
          <a-form-item label="环境名称" required>
            <a-input v-model:value="envForm.name" />
          </a-form-item>
          <a-form-item label="基础 URL" required>
            <a-input v-model:value="envForm.base_url" placeholder="https://example.com" />
          </a-form-item>
          <a-form-item label="描述">
            <a-textarea v-model:value="envForm.description" :rows="2" />
          </a-form-item>
          <a-form-item label="设为默认环境">
            <a-switch v-model:checked="envForm.is_default" />
          </a-form-item>
        </a-form>
      </a-modal>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, EnvironmentOutlined
} from '@ant-design/icons-vue'
import {
  testPlansApi, testPlanExecutionsApi,
  getEnvironments, createEnvironment, updateEnvironment, deleteEnvironment,
  type TestPlan, type TestEnvironment
} from '@/api/testPlans'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const loading = ref(false)
const plans = ref<TestPlan[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const versions = ref<ProjectVersion[]>([])
const filterName = ref('')
const filterStatus = ref<string | undefined>(undefined)
const filterPriority = ref<string | undefined>(undefined)
const filterVersionId = ref<number | undefined>(undefined)

const showCreateModal = ref(false)
const submitting = ref(false)

const formData = ref({
  name: '',
  description: '',
  priority: 'P2',
  environment_id: null as number | null,
  version_id: null as number | null,
  schedule_type: 'manual',
})

// 环境管理
const showEnvModal = ref(false)
const showEnvCreate = ref(false)
const envSubmitting = ref(false)
const editingEnv = ref<TestEnvironment | null>(null)
const environments = ref<TestEnvironment[]>([])
const envForm = ref({
  name: '',
  base_url: '',
  description: '',
  is_default: false
})

const columns = [
  { title: '计划名称', dataIndex: 'name', key: 'name' },
  { title: '所属版本', dataIndex: 'version_id', key: 'version', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '节点数', dataIndex: 'total_cases', key: 'total_cases', width: 80 },
  { title: '最近通过率', dataIndex: 'last_pass_rate', key: 'last_pass_rate', width: 120 },
  { title: '最近执行', dataIndex: 'last_execution_id', key: 'last_execution_id', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 280, fixed: 'right' as const }
]

const envColumns = [
  { title: '环境名称', dataIndex: 'name', key: 'name' },
  { title: '基础URL', dataIndex: 'base_url', key: 'base_url' },
  { title: '默认', dataIndex: 'is_default', key: 'is_default', width: 80 },
  { title: '操作', key: 'action', width: 120 }
]

function getVersionName(versionId?: number | null) {
  if (!versionId) return '-'
  return versions.value.find(v => v.id === versionId)?.name || '-'
}

function getStatusColor(status?: string) {
  const map: Record<string, string> = {
    draft: 'default',
    scheduled: 'blue',
    running: 'processing',
    completed: 'success',
    failed: 'error',
    archived: 'default'
  }
  return map[status || ''] || 'default'
}

function getStatusText(status?: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    scheduled: '已排期',
    running: '执行中',
    completed: '已完成',
    failed: '已失败',
    archived: '已归档'
  }
  return map[status || ''] || status
}

function getPriorityColor(priority?: string) {
  const map: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return map[priority || ''] || 'default'
}

async function loadPlans() {
  loading.value = true
  try {
    const res = await testPlansApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: filterName.value || undefined,
      status: filterStatus.value,
      priority: filterPriority.value,
      version_id: filterVersionId.value
    })
    plans.value = res.items
    pagination.value.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  filterName.value = ''
  filterStatus.value = undefined
  filterPriority.value = undefined
  filterVersionId.value = undefined
  loadPlans()
}

async function loadEnvironments() {
  try {
    environments.value = await getEnvironments(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载环境失败')
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadPlans()
}

function openCreateModal() {
  resetForm()
  showCreateModal.value = true
}

function resetForm() {
  formData.value = {
    name: '',
    description: '',
    priority: 'P2',
    environment_id: null,
    version_id: null,
    schedule_type: 'manual',
  }
}

async function handleSubmit() {
  if (!formData.value.name) {
    message.warning('请输入计划名称')
    return
  }
  submitting.value = true
  try {
    const created = await testPlansApi.create(projectId, formData.value)
    message.success('创建成功，请编排节点')
    showCreateModal.value = false
    // 创建后直接跳转到编排页进行节点编排
    router.push(`/projects/${projectId}/test-plans/${created.id}/edit`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

function editPlan(record: TestPlan) {
  // 编辑直接跳转到编排页
  router.push(`/projects/${projectId}/test-plans/${record.id}/edit`)
}

async function handleDelete(record: TestPlan) {
  try {
    await testPlansApi.delete(projectId, record.id!)
    message.success('删除成功')
    loadPlans()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleExecute(record: TestPlan) {
  try {
    const res = await testPlanExecutionsApi.run(projectId, record.id!)
    message.success('计划已启动')
    router.push(`/projects/${projectId}/test-plans/${record.id}/run/${res.execution_id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
  }
}

function viewReport(record: TestPlan) {
  if (record.last_execution_id) {
    router.push(`/projects/${projectId}/test-plans/${record.id}/report/${record.last_execution_id}`)
  }
}

// 环境管理
function editEnv(record: TestEnvironment) {
  editingEnv.value = record
  envForm.value = {
    name: record.name,
    base_url: record.base_url,
    description: record.description || '',
    is_default: record.is_default || false
  }
  showEnvCreate.value = true
}

function resetEnvForm() {
  editingEnv.value = null
  envForm.value = { name: '', base_url: '', description: '', is_default: false }
}

async function submitEnv() {
  if (!envForm.value.name || !envForm.value.base_url) {
    message.warning('请填写环境名称和URL')
    return
  }
  envSubmitting.value = true
  try {
    if (editingEnv.value) {
      await updateEnvironment(projectId, editingEnv.value.id!, envForm.value)
      message.success('更新成功')
    } else {
      await createEnvironment(projectId, envForm.value)
      message.success('创建成功')
    }
    showEnvCreate.value = false
    resetEnvForm()
    loadEnvironments()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    envSubmitting.value = false
  }
}

async function deleteEnv(record: TestEnvironment) {
  try {
    await deleteEnvironment(projectId, record.id!)
    message.success('删除成功')
    loadEnvironments()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function loadVersions() {
  try {
    versions.value = (await getVersions(projectId, { page_size: 200 })).items
  } catch (e) {
    console.error('加载版本列表失败', e)
  }
}

onMounted(() => {
  const params = { keyword: '', status: undefined, priority: undefined, version_id: undefined as number | undefined }
  filterName.value = params.keyword || ''
  filterStatus.value = params.status
  filterPriority.value = params.priority
  filterVersionId.value = params.version_id ? Number(params.version_id) : undefined
  loadPlans()
  loadEnvironments()
  loadVersions()
})
</script>

<style scoped>
.plans-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
</style>
