<template>
  <div class="plans-page">
    <div class="page-header">
      <h2>测试计划管理</h2>
      <div>
        <a-button @click="showEnvModal = true" style="margin-right: 8px">
          <EnvironmentOutlined /> 环境管理
        </a-button>
        <a-button type="primary" @click="showCreateModal = true">
          <PlusOutlined /> 新建计划
        </a-button>
      </div>
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
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">{{ getStatusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'priority'">
            <a-tag :color="getPriorityColor(record.priority)">{{ record.priority }}</a-tag>
          </template>
          <template v-else-if="column.key === 'pass_rate'">
            <a-progress :percent="record.pass_rate || 0" size="small" />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="viewPlan(record)">详情</a-button>
            <a-button type="link" size="small" @click="editPlan(record)">编辑</a-button>
            <a-button type="link" size="small" @click="handleExecute(record)" :disabled="record.status === 'running'">
              执行
            </a-button>
            <a-popconfirm title="确定删除该计划？" @confirm="handleDelete(record)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建/编辑计划弹窗 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingPlan ? '编辑测试计划' : '新建测试计划'"
      width="700px"
      @ok="handleSubmit"
      :confirm-loading="submitting"
    >
      <a-form layout="vertical" :model="formData">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="计划名称" required>
              <a-input v-model:value="formData.name" placeholder="请输入计划名称" />
            </a-form-item>
          </a-col>
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
        </a-row>
        <a-form-item label="计划描述">
          <a-textarea v-model:value="formData.description" :rows="3" placeholder="请输入计划描述" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="测试环境">
              <a-select v-model:value="formData.environment_id" allow-clear placeholder="选择测试环境">
                <a-select-option v-for="env in environments" :key="env.id" :value="env.id">
                  {{ env.name }} ({{ env.base_url }})
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="调度类型">
              <a-select v-model:value="formData.schedule_type">
                <a-select-option value="manual">手动执行</a-select-option>
                <a-select-option value="once">一次性执行</a-select-option>
                <a-select-option value="cron">定时执行</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="开始时间">
              <a-date-picker v-model:value="formData.start_date" show-time style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="结束时间">
              <a-date-picker v-model:value="formData.end_date" show-time style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="关联用例">
          <a-select
            v-model:value="formData.case_ids"
            mode="multiple"
            placeholder="选择要关联的测试用例"
            :filter-option="filterCaseOption"
            style="width: 100%"
          >
            <a-select-option v-for="c in allCases" :key="c.id" :value="c.id">
              [{{ c.priority }}] {{ c.title }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 计划详情弹窗 -->
    <a-modal v-model:open="showDetailModal" title="计划详情" width="800px" :footer="null">
      <div v-if="currentPlan">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="计划名称">{{ currentPlan.name }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="getStatusColor(currentPlan.status)">{{ getStatusText(currentPlan.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="优先级">{{ currentPlan.priority }}</a-descriptions-item>
          <a-descriptions-item label="通过率">{{ currentPlan.pass_rate }}%</a-descriptions-item>
          <a-descriptions-item label="用例总数">{{ currentPlan.total_cases }}</a-descriptions-item>
          <a-descriptions-item label="通过/失败">{{ currentPlan.passed_cases }} / {{ currentPlan.failed_cases }}</a-descriptions-item>
        </a-descriptions>
        <a-divider>关联用例</a-divider>
        <a-table
          :columns="caseColumns"
          :data-source="planCases"
          :loading="casesLoading"
          size="small"
          :pagination="false"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getCaseStatusColor(record.status)">{{ record.status }}</a-tag>
            </template>
          </template>
        </a-table>
      </div>
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined, EnvironmentOutlined
} from '@ant-design/icons-vue'
import {
  getPlans, createPlan, updatePlan, deletePlan, executePlan,
  getPlanCases, getEnvironments, createEnvironment, updateEnvironment, deleteEnvironment,
  type TestPlan, type TestPlanCase, type TestEnvironment
} from '@/api/testPlans'
import { getCases, type TestCase } from '@/api/cases'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const plans = ref<TestPlan[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const showCreateModal = ref(false)
const showDetailModal = ref(false)
const submitting = ref(false)
const editingPlan = ref<TestPlan | null>(null)
const currentPlan = ref<TestPlan | null>(null)
const planCases = ref<TestPlanCase[]>([])
const casesLoading = ref(false)
const allCases = ref<TestCase[]>([])

const formData = ref({
  name: '',
  description: '',
  priority: 'P2',
  environment_id: null as number | null,
  schedule_type: 'manual',
  schedule_cron: '',
  start_date: null as any,
  end_date: null as any,
  case_ids: [] as number[]
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
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '用例数', dataIndex: 'total_cases', key: 'total_cases', width: 80 },
  { title: '通过率', dataIndex: 'pass_rate', key: 'pass_rate', width: 150 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' as const }
]

const caseColumns = [
  { title: '序号', dataIndex: 'sort_order', key: 'sort_order', width: 60 },
  { title: '用例标题', dataIndex: 'case_title', key: 'case_title' },
  { title: '优先级', dataIndex: 'case_priority', key: 'case_priority', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 }
]

const envColumns = [
  { title: '环境名称', dataIndex: 'name', key: 'name' },
  { title: '基础URL', dataIndex: 'base_url', key: 'base_url' },
  { title: '默认', dataIndex: 'is_default', key: 'is_default', width: 80 },
  { title: '操作', key: 'action', width: 120 }
]

function getStatusColor(status?: string) {
  const map: Record<string, string> = {
    draft: 'default',
    scheduled: 'blue',
    running: 'processing',
    completed: 'success',
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
    archived: '已归档'
  }
  return map[status || ''] || status
}

function getPriorityColor(priority?: string) {
  const map: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return map[priority || ''] || 'default'
}

function getCaseStatusColor(status?: string) {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    passed: 'success',
    failed: 'error',
    skipped: 'warning'
  }
  return map[status || ''] || 'default'
}

function filterCaseOption(input: string, option: any) {
  return (option.children || '').toLowerCase().includes(input.toLowerCase())
}

async function loadPlans() {
  loading.value = true
  try {
    const res = await getPlans(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize
    })
    plans.value = res.items
    pagination.value.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadEnvironments() {
  try {
    environments.value = await getEnvironments(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载环境失败')
  }
}

async function loadAllCases() {
  try {
    allCases.value = await getCases(projectId)
  } catch (e: any) {
    console.error('加载用例失败', e)
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadPlans()
}

function editPlan(record: TestPlan) {
  editingPlan.value = record
  formData.value = {
    name: record.name,
    description: record.description || '',
    priority: record.priority || 'P2',
    environment_id: record.environment_id || null,
    schedule_type: record.schedule_type || 'manual',
    schedule_cron: record.schedule_cron || '',
    start_date: record.start_date ? new Date(record.start_date) : null,
    end_date: record.end_date ? new Date(record.end_date) : null,
    case_ids: []
  }
  showCreateModal.value = true
}

function resetForm() {
  editingPlan.value = null
  formData.value = {
    name: '',
    description: '',
    priority: 'P2',
    environment_id: null,
    schedule_type: 'manual',
    schedule_cron: '',
    start_date: null,
    end_date: null,
    case_ids: []
  }
}

async function handleSubmit() {
  if (!formData.value.name) {
    message.warning('请输入计划名称')
    return
  }
  submitting.value = true
  try {
    const data: any = { ...formData.value }
    if (data.start_date) data.start_date = data.start_date.toISOString()
    if (data.end_date) data.end_date = data.end_date.toISOString()

    if (editingPlan.value) {
      await updatePlan(projectId, editingPlan.value.id!, data)
      message.success('更新成功')
    } else {
      await createPlan(projectId, data)
      message.success('创建成功')
    }
    showCreateModal.value = false
    resetForm()
    loadPlans()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(record: TestPlan) {
  try {
    await deletePlan(projectId, record.id!)
    message.success('删除成功')
    loadPlans()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleExecute(record: TestPlan) {
  try {
    await executePlan(projectId, record.id!)
    message.success('计划已启动')
    loadPlans()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
  }
}

async function viewPlan(record: TestPlan) {
  currentPlan.value = record
  showDetailModal.value = true
  casesLoading.value = true
  try {
    planCases.value = await getPlanCases(projectId, record.id!)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载用例失败')
  } finally {
    casesLoading.value = false
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

onMounted(() => {
  loadPlans()
  loadEnvironments()
  loadAllCases()
})
</script>

<style scoped>
.plans-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
</style>
