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
      <a-input v-model:value="filterTitle" placeholder="用例名称" allow-clear style="width: 180px" />
      <a-select v-model:value="filterCaseType" placeholder="类型" allow-clear style="width: 120px" :options="caseTypeOptions" />
      <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px" :options="statusOptions" />
      <a-select v-model:value="filterPriority" placeholder="优先级" allow-clear style="width: 120px" :options="priorityOptions" />
      <a-input v-model:value="filterModule" placeholder="模块" allow-clear style="width: 150px" />
      <a-select v-model:value="filterReqId" placeholder="关联需求" allow-clear show-search style="width: 200px"
        :options="requirements.map(req => ({ label: req.title, value: req.id }))" />
      <a-button type="primary" @click="fetchCases">查询</a-button>
      <a-button @click="handleReset">重置</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :columns="columns"
        :data-source="cases"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
        size="middle"
        :scroll="{ x: 1200 }"
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
          <template v-else-if="column.key === 'requirement'">
            <a-tooltip v-if="getReqTitle(record.req_id)" placement="topLeft" :overlay-style="{ maxWidth: '300px' }">
              <template #title>{{ getReqTitle(record.req_id) }}</template>
              <span class="cell-ellipsis">{{ getReqTitle(record.req_id) }}</span>
            </a-tooltip>
            <span v-else style="color: #999">-</span>
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
      width="750px"
      :ok-text="selectedReqId && featureModules.length > 0 ? '按勾选功能点生成' : '生成'"
    >
      <a-form layout="vertical">
        <a-form-item label="选择需求" required>
          <a-select
            v-model:value="selectedReqId"
            placeholder="选择已有需求（必选）"
            :options="requirements.map(req => ({ label: req.title, value: req.id }))"
            @change="onReqChange"
          />
        </a-form-item>

        <!-- 功能点展示 -->
        <template v-if="selectedReqId">
          <a-spin :spinning="loadingFeatures">
            <template v-if="featureModules.length > 0">
              <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 500;">已拆分功能点（按模块分组）</span>
                <a-space>
                  <a-button size="small" @click="selectAllFeatures">全选</a-button>
                  <a-button size="small" @click="invertFeatures">反选</a-button>
                  <span style="color: #999; font-size: 12px;">已选 {{ selectedFeatureIds.length }} 个</span>
                </a-space>
              </div>
              <div v-for="mod in featureModules" :key="mod.module_name" style="margin-bottom: 12px;">
                <div style="font-weight: 500; margin-bottom: 4px; color: #1677ff;">
                  {{ mod.module_name }}
                  <a-button size="small" type="link" @click="toggleModule(mod)">切换</a-button>
                </div>
                <a-checkbox-group v-model:value="selectedFeatureIds" style="width: 100%;">
                  <a-row>
                    <a-col v-for="feat in mod.features" :key="feat.id" :span="12" style="margin-bottom: 4px;">
                      <a-checkbox :value="feat.id">
                        <span>{{ feat.name }}</span>
                        <a-tag :color="feat.priority === 'P0' ? 'red' : feat.priority === 'P1' ? 'orange' : 'blue'" style="margin-left: 4px; font-size: 11px;">{{ feat.priority }}</a-tag>
                      </a-checkbox>
                    </a-col>
                  </a-row>
                </a-checkbox-group>
              </div>
            </template>
            <template v-else-if="!loadingFeatures">
              <a-alert
                message="该需求尚未拆分功能点"
                description="功能点拆分是异步的，如果刚创建需求请稍等片刻。也可以点击下方按钮手动触发拆分。"
                type="info"
                show-icon
                style="margin-bottom: 12px;"
              />
              <a-button type="primary" size="small" :loading="splitting" @click="triggerSplit">触发功能点拆分</a-button>
            </template>
          </a-spin>
        </template>

        <a-row :gutter="16" style="margin-top: 12px;">
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
          <a-col :span="12">
            <a-form-item label="Prompt 模板">
              <a-select
                v-model:value="selectedPromptId"
                placeholder="使用默认 Prompt"
                allow-clear
                :options="prompts.map(p => ({ label: p.name + (p.is_default ? '（默认）' : ''), value: p.id }))"
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
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { getCases, createCase, updateCase, deleteCase as deleteCaseApi, generateCases, generateCasesStatus, getRequirements, getFeatures, splitFeatures, type FeatureModuleGroup } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const saving = ref(false)
const cases = ref<any[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
}
const requirements = ref<any[]>([])
const llmConfigs = ref<any[]>([])

const filterPriority = ref<string | undefined>(undefined)
const filterModule = ref('')
const filterTitle = ref('')
const filterCaseType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const filterReqId = ref<number | undefined>(undefined)

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
const selectedLLMConfig = ref<number | null>(null)
const prompts = ref<Prompt[]>([])
const selectedPromptId = ref<number | null>(null)

// 功能点相关
const featureModules = ref<FeatureModuleGroup[]>([])
const selectedFeatureIds = ref<number[]>([])
const loadingFeatures = ref(false)
const splitting = ref(false)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '用例名称', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 120 },
  { title: '关联需求', key: 'requirement', width: 180, ellipsis: true },
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

function getReqTitle(reqId: number | null | undefined) {
  if (!reqId) return ''
  const req = requirements.value.find((r: any) => r.id === reqId)
  return req ? req.title : ''
}

async function fetchCases() {
  syncToUrl({ priority: filterPriority.value, module: filterModule.value, title: filterTitle.value, case_type: filterCaseType.value, status: filterStatus.value, req_id: filterReqId.value })
  loading.value = true
  try {
    const params: any = {}
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterModule.value) params.module = filterModule.value
    if (filterTitle.value) params.title = filterTitle.value
    if (filterCaseType.value) params.case_type = filterCaseType.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterReqId.value) params.req_id = filterReqId.value
    cases.value = await getCases(projectId, params)
    pagination.total = cases.value.length
  } finally {
    loading.value = false
  }
}

function handleReset() {
  filterPriority.value = undefined
  filterModule.value = ''
  filterTitle.value = ''
  filterCaseType.value = undefined
  filterStatus.value = undefined
  filterReqId.value = undefined
  fetchCases()
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

async function onReqChange(reqId: any) {
  featureModules.value = []
  selectedFeatureIds.value = []
  if (!reqId) return
  loadingFeatures.value = true
  try {
    const data = await getFeatures(projectId, Number(reqId))
    if (data.split_status === 'completed' || data.modules?.length > 0) {
      featureModules.value = data.modules || []
      // 默认全选
      selectedFeatureIds.value = featureModules.value.flatMap(m => m.features.map(f => f.id))
    } else if (data.split_status === 'processing') {
      message.info('功能点拆分中，请稍后重试')
    }
  } catch (e: any) {
    message.warning('获取功能点失败：' + (e.message || '未知错误'))
  } finally {
    loadingFeatures.value = false
  }
}

function selectAllFeatures() {
  selectedFeatureIds.value = featureModules.value.flatMap(m => m.features.map(f => f.id))
}

function invertFeatures() {
  const allIds = featureModules.value.flatMap(m => m.features.map(f => f.id))
  selectedFeatureIds.value = allIds.filter(id => !selectedFeatureIds.value.includes(id))
}

function toggleModule(mod: FeatureModuleGroup) {
  const modIds = mod.features.map(f => f.id)
  const allSelected = modIds.every(id => selectedFeatureIds.value.includes(id))
  if (allSelected) {
    selectedFeatureIds.value = selectedFeatureIds.value.filter(id => !modIds.includes(id))
  } else {
    const set = new Set(selectedFeatureIds.value)
    modIds.forEach(id => set.add(id))
    selectedFeatureIds.value = Array.from(set)
  }
}

async function triggerSplit() {
  if (!selectedReqId.value) return
  splitting.value = true
  try {
    await splitFeatures(projectId, selectedReqId.value)
    message.success('功能点拆分任务已提交，请等待几秒后重新选择需求')
  } catch (e: any) {
    message.error('触发拆分失败：' + (e.message || '未知错误'))
  } finally {
    splitting.value = false
  }
}

async function doGenerate() {
  if (!selectedReqId.value) {
    message.warning('请选择需求')
    return
  }
  if (featureModules.value.length > 0 && selectedFeatureIds.value.length === 0) {
    message.warning('请至少勾选一个功能点')
    return
  }
  generating.value = true
  try {
    const params: any = {
      requirement_id: selectedReqId.value,
      llm_config_id: selectedLLMConfig.value || undefined,
      prompt_id: selectedPromptId.value || undefined
    }
    if (selectedFeatureIds.value.length > 0) {
      params.feature_ids = selectedFeatureIds.value
    } else {
      params.count = 10
      params.content = ''
    }
    const result = await generateCases(projectId, params)
    message.success(`用例生成任务已提交（任务ID: ${result.task_id}），按 ${featureModules.value.length} 个模块分批生成`)
    showGenerateModal.value = false
    selectedReqId.value = null
    featureModules.value = []
    selectedFeatureIds.value = []
    selectedPromptId.value = null
    setTimeout(() => fetchCases(), 5000)
  } catch (e: any) {
    message.error('提交生成任务失败：' + (e.message || '未知错误'))
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  const params = loadFromUrl({ priority: undefined, module: '', title: '', case_type: undefined, status: undefined, req_id: undefined })
  filterPriority.value = params.priority
  filterModule.value = params.module || ''
  filterTitle.value = params.title || ''
  filterCaseType.value = params.case_type
  filterStatus.value = params.status
  filterReqId.value = params.req_id ? Number(params.req_id) : undefined
  fetchCases()
  getRequirements(projectId).then(data => { requirements.value = data })
  getLLMConfigs().then(data => { llmConfigs.value = data })
  promptsApi.list('case_generation').then(data => { prompts.value = data }).catch(() => {})
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}

.cell-ellipsis {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
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
