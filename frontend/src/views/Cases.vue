<template>
  <div class="page-container">
    <div class="page-header">
      <h2>测试用例管理</h2>
      <div class="header-actions">
        <a-button @click="showGenerateModal = true" style="margin-right: 8px">
          <template #icon>
            <ThunderboltOutlined />
          </template>
          AI 生成用例
        </a-button>
        <a-button type="primary" @click="openCreateDialog">
          <template #icon>
            <PlusOutlined />
          </template>
          新建用例
        </a-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <a-select
        v-model:value="filterPriority"
        placeholder="优先级"
        allow-clear
        style="width: 120px"
        @change="fetchCases"
        :options="priorityOptions"
      />
      <a-input
        v-model:value="filterModule"
        placeholder="模块"
        allow-clear
        style="width: 150px"
        @change="fetchCases"
      />
      <a-button type="primary" @click="fetchCases">查询</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :columns="columns"
        :data-source="cases"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 1000 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'case_type'">
            {{ caseTypeLabel(record.case_type) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="runCase(record)">执行</a-button>
            <a-button type="link" size="small" @click="editCase(record)">编辑</a-button>
            <a-button type="link" size="small" danger @click="deleteCase(record)">删除</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- 新建/编辑用例对话框 -->
    <a-modal
      v-model:open="showCaseModal"
      :title="editingCase ? '编辑用例' : '新建用例'"
      @ok="saveCase"
      :confirm-loading="saving"
      width="720px"
    >
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item label="用例名称" required>
              <a-input v-model:value="caseForm.title" placeholder="请输入用例名称" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="模块">
              <a-input v-model:value="caseForm.module" placeholder="所属模块" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="优先级">
              <a-select v-model:value="caseForm.priority" :options="priorityOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="用例类型">
              <a-select v-model:value="caseForm.case_type" :options="caseTypeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="状态">
              <a-select v-model:value="caseForm.status" :options="statusOptions" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="前置条件">
          <a-textarea v-model:value="caseForm.preconditions" :rows="2" placeholder="测试前置条件" />
        </a-form-item>
        <a-form-item label="测试步骤">
          <div class="steps-editor">
            <div v-for="(step, idx) in caseForm.steps" :key="idx" class="step-row">
              <span class="step-num">{{ idx + 1 }}</span>
              <a-input v-model:value="step.action" placeholder="操作" style="flex: 1" />
              <a-input v-model:value="step.expected" placeholder="预期结果" style="flex: 1; margin-left: 8px" />
              <a-button
                type="text"
                danger
                :icon="h(DeleteOutlined)"
                @click="caseForm.steps.splice(idx, 1)"
                style="margin-left: 8px"
              />
            </div>
            <a-button type="dashed" block @click="caseForm.steps.push({ action: '', expected: '' })">
              <template #icon>
                <PlusOutlined />
              </template>
              添加步骤
            </a-button>
          </div>
        </a-form-item>
        <a-form-item label="预期结果">
          <a-textarea v-model:value="caseForm.expected_result" :rows="2" placeholder="最终预期结果" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- AI 生成用例对话框 -->
    <a-modal
      v-model:open="showGenerateModal"
      title="AI 生成测试用例"
      @ok="doGenerate"
      :confirm-loading="generating"
      width="600px"
    >
      <a-form layout="vertical">
        <a-form-item label="选择需求">
          <a-select
            v-model:value="selectedReqId"
            placeholder="选择已有需求"
            allow-clear
            :options="requirements.map(req => ({ label: req.title, value: req.id }))"
          />
        </a-form-item>
        <a-form-item label="或直接输入需求描述">
          <a-textarea
            v-model:value="generateContent"
            :rows="5"
            placeholder="输入需求描述，AI 将根据此生成用例"
          />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="生成数量">
              <a-input-number v-model:value="generateCount" :min="1" :max="50" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="模型配置">
              <a-select
                v-model:value="selectedLLMConfig"
                placeholder="使用默认模型"
                allow-clear
                :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, reactive, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { getCases, createCase, updateCase, deleteCase as deleteCaseApi, generateCases, getRequirements, batchCreateCases } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const loading = ref(false)
const saving = ref(false)
const cases = ref<any[]>([])
const requirements = ref<any[]>([])
const llmConfigs = ref<any[]>([])

const filterPriority = ref<string | undefined>(undefined)
const filterModule = ref('')

const showCaseModal = ref(false)
const editingCase = ref<any>(null)
const caseForm = reactive({
  title: '',
  module: '',
  priority: 'P1',
  case_type: 'functional',
  status: 'draft',
  preconditions: '',
  steps: [{ action: '', expected: '' }] as any[],
  expected_result: ''
})

const showGenerateModal = ref(false)
const generating = ref(false)
const selectedReqId = ref<number | null>(null)
const generateContent = ref('')
const generateCount = ref(10)
const selectedLLMConfig = ref<number | null>(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '用例名称', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 120 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '类型', dataIndex: 'case_type', key: 'case_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 140, fixed: 'right' }
]

const priorityOptions = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' }
]

const caseTypeOptions = [
  { label: '功能测试', value: 'functional' },
  { label: '性能测试', value: 'performance' },
  { label: '安全测试', value: 'security' }
]

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '生效', value: 'active' },
  { label: '归档', value: 'archived' }
]

function priorityColor(p: string) {
  const map: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return map[p] || 'default'
}

function statusColor(s: string) {
  const map: Record<string, string> = { draft: 'default', active: 'green', archived: 'gray' }
  return map[s] || 'default'
}

function statusLabel(s: string) {
  const map: Record<string, string> = { draft: '草稿', active: '生效', archived: '归档' }
  return map[s] || s
}

function caseTypeLabel(t: string) {
  const map: Record<string, string> = { functional: '功能测试', performance: '性能测试', security: '安全测试' }
  return map[t] || t
}

async function fetchCases() {
  loading.value = true
  try {
    const params: any = {}
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterModule.value) params.module = filterModule.value
    cases.value = await getCases(projectId, params)
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  editingCase.value = null
  Object.assign(caseForm, {
    title: '', module: '', priority: 'P1', case_type: 'functional',
    status: 'draft', preconditions: '', steps: [{ action: '', expected: '' }], expected_result: ''
  })
  showCaseModal.value = true
}

function editCase(row: any) {
  editingCase.value = row
  Object.assign(caseForm, {
    title: row.title,
    module: row.module,
    priority: row.priority,
    case_type: row.case_type,
    status: row.status,
    preconditions: row.preconditions,
    steps: typeof row.steps === 'string' ? JSON.parse(row.steps || '[]') : (row.steps || []),
    expected_result: row.expected_result
  })
  showCaseModal.value = true
}

async function saveCase() {
  if (!caseForm.title.trim()) {
    message.warning('请输入用例名称')
    return
  }
  saving.value = true
  try {
    if (editingCase.value) {
      await updateCase(projectId, editingCase.value.id, caseForm)
      message.success('更新成功')
    } else {
      await createCase(projectId, caseForm)
      message.success('创建成功')
    }
    showCaseModal.value = false
    fetchCases()
  } finally {
    saving.value = false
  }
}

function runCase(row: any) {
  // 将用例步骤转换为自然语言指令
  let instruction = `执行测试用例：${row.title}\n`
  if (row.preconditions) {
    instruction += `前置条件：${row.preconditions}\n`
  }
  try {
    const steps = typeof row.steps === 'string' ? JSON.parse(row.steps) : row.steps
    if (Array.isArray(steps) && steps.length > 0) {
      instruction += '测试步骤：\n'
      steps.forEach((step: any, idx: number) => {
        instruction += `${idx + 1}. ${step.action || ''}`
        if (step.expected) {
          instruction += `（预期：${step.expected}）`
        }
        instruction += '\n'
      })
    }
  } catch (e) {
    // steps 解析失败，忽略
  }
  if (row.expected_result) {
    instruction += `最终预期结果：${row.expected_result}`
  }

  // 跳转到执行页面，携带用例信息
  router.push({
    path: `/projects/${projectId}/execution`,
    query: {
      caseId: row.id,
      caseTitle: row.title,
      instruction: encodeURIComponent(instruction)
    }
  })
}

function deleteCase(row: any) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除用例「${row.title}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteCaseApi(projectId, row.id)
      message.success('删除成功')
      fetchCases()
    }
  })
}

async function doGenerate() {
  if (!selectedReqId.value && !generateContent.value.trim()) {
    message.warning('请选择需求或输入需求内容')
    return
  }
  generating.value = true
  try {
    const result: any = await generateCases(projectId, {
      requirement_id: selectedReqId.value || undefined,
      content: generateContent.value,
      count: generateCount.value,
      llm_config_id: selectedLLMConfig.value || undefined
    })
    const generatedCases = result.cases || []
    if (generatedCases.length > 0) {
      await batchCreateCases(projectId, generatedCases)
    }
    message.success(`成功生成并保存 ${generatedCases.length} 条用例`)
    showGenerateModal.value = false
    generateContent.value = ''
    selectedReqId.value = null
    fetchCases()
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  fetchCases()
  getRequirements(projectId).then(data => { requirements.value = data })
  getLLMConfigs().then(data => { llmConfigs.value = data })

  const generated = sessionStorage.getItem('generated_cases')
  if (generated) {
    sessionStorage.removeItem('generated_cases')
    const cases = JSON.parse(generated)
    if (cases.length > 0) {
      batchCreateCases(projectId, cases).then(() => {
        message.success(`已保存 ${cases.length} 条生成的用例`)
        fetchCases()
      })
    }
  }
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.steps-editor {
  width: 100%;
}

.step-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 0;
}

.step-num {
  width: 28px;
  text-align: center;
  color: rgba(0, 0, 0, 0.45);
  font-size: 14px;
  flex-shrink: 0;
}
</style>
