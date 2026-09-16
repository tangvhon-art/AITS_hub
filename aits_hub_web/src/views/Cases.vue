<template>
  <div class="page-container">
    <PageHeader title="测试用例管理">
      <template #extra>
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
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="用例名称">
          <a-input v-model:value="filterTitle" placeholder="用例名称" allow-clear style="width: 180px" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="filterCaseType" placeholder="类型" allow-clear style="width: 120px" :options="caseTypeOptions" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px" :options="statusOptions" />
        </a-form-item>
        <a-form-item label="优先级">
          <a-select v-model:value="filterPriority" placeholder="优先级" allow-clear style="width: 120px" :options="priorityOptions" />
        </a-form-item>
        <a-form-item label="模块">
          <a-input v-model:value="filterModule" placeholder="模块" allow-clear style="width: 150px" />
        </a-form-item>
        <a-form-item label="关联需求">
          <a-select v-model:value="filterReqId" placeholder="关联需求" allow-clear show-search style="width: 200px"
            :options="requirements.map(req => ({ label: req.title, value: req.id }))" />
        </a-form-item>
      </a-form>
    </SearchBar>

    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      size="middle"
      :scroll="{ x: 1200 }"
      :row-selection="rowSelection"
      @change="handleTableChange"
    >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
      <template #title>
        <div v-if="selectedRowKeys.length > 0" style="display: flex; align-items: center; gap: 8px;">
          <span>已选 {{ selectedRowKeys.length }} 项</span>
          <a-select
            v-model:value="batchStatus"
            placeholder="批量修改状态"
            style="width: 140px"
            :options="statusOptions"
            @change="onBatchStatusChange"
          />
          <a-button size="small" @click="selectedRowKeys = []">取消选择</a-button>
        </div>
      </template>
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
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.title)">删除</a-button>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 新建/编辑用例对话框 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑用例' : '新建用例'"
      :loading="modalLoading"
      width="720px"
      @ok="submit"
    >
      <a-form-item label="用例名称" required>
        <a-input v-model:value="formData.title" placeholder="请输入用例名称" />
      </a-form-item>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="关联需求">
            <a-select v-model:value="formData.req_id" placeholder="选择需求" allow-clear show-search style="width: 100%"
              :options="requirements.map(req => ({ label: req.title, value: req.id }))" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="模块">
            <a-input v-model:value="formData.module" placeholder="所属模块" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="优先级">
            <a-select v-model:value="formData.priority" :options="priorityOptions" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="用例类型">
            <a-select v-model:value="formData.case_type" :options="caseTypeOptions" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="状态">
            <a-select v-model:value="formData.status" :options="statusOptions" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="前置条件">
        <a-textarea v-model:value="formData.preconditions" :rows="2" placeholder="测试前置条件" />
      </a-form-item>
      <a-form-item label="测试步骤">
        <div class="steps-editor">
          <div v-for="(step, idx) in formData.steps" :key="idx" class="step-row">
            <span class="step-num">{{ idx + 1 }}</span>
            <a-input v-model:value="step.action" placeholder="操作" style="flex: 1" />
            <a-input v-model:value="step.expected" placeholder="预期结果" style="flex: 1; margin-left: 8px" />
            <a-button
              type="text"
              danger
              :icon="h(DeleteOutlined)"
              @click="formData.steps.splice(idx, 1)"
              style="margin-left: 8px"
            />
          </div>
          <a-button type="dashed" block @click="formData.steps.push({ action: '', expected: '' })">
            <template #icon>
              <PlusOutlined />
            </template>
            添加步骤
          </a-button>
        </div>
      </a-form-item>
      <a-form-item label="预期结果">
        <a-textarea v-model:value="formData.expected_result" :rows="2" placeholder="最终预期结果" />
      </a-form-item>
    </FormModal>

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
        <a-form-item v-if="showCaseBackend" label="执行方式">
          <a-radio-group v-model:value="caseBackend" :options="AI_BACKEND_OPTIONS" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { getCases, createCase, updateCase, deleteCase as deleteCaseApi, generateCases, getRequirements, getFeatures, splitFeatures, batchUpdateStatus, type FeatureModuleGroup } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'
import { useWorkflowBackend } from '@/composables/useWorkflowBackend'
import { AI_BACKEND_OPTIONS } from '@/constants/enums'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'

const { showBackendOption: showCaseBackend, defaultBackend: caseDefaultBackend, fetch: fetchCaseBackend } = useWorkflowBackend()
const caseBackend = ref('local')

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const selectedRowKeys = ref<number[]>([])
const batchStatus = ref<string | undefined>(undefined)

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: number[]) => { selectedRowKeys.value = keys },
}))

async function onBatchStatusChange(val: string) {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先勾选用例')
    batchStatus.value = undefined
    return
  }
  try {
    const res = await batchUpdateStatus(projectId, selectedRowKeys.value, val)
    message.success(`成功更新 ${res.updated} 条用例状态`)
    selectedRowKeys.value = []
    batchStatus.value = undefined
    loadData()
  } catch {
    message.error('批量更新失败')
    batchStatus.value = undefined
  }
}

const requirements = ref<any[]>([])
const llmConfigs = ref<any[]>([])

const filterPriority = ref<string | undefined>(undefined)
const filterModule = ref('')
const filterTitle = ref('')
const filterCaseType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const filterReqId = ref<number | undefined>(undefined)

// ── 列表（后端返回全量，包装为 useList 统一形态）──
const { loading, list, total, pagination, loadData, handleTableChange } = useList<any>(
  async (params) => {
    const query: any = {}
    if (filterPriority.value) query.priority = filterPriority.value
    if (filterModule.value) query.module = filterModule.value
    if (filterTitle.value) query.title = filterTitle.value
    if (filterCaseType.value) query.case_type = filterCaseType.value
    if (filterStatus.value) query.status = filterStatus.value
    if (filterReqId.value) query.req_id = filterReqId.value
    const data = await getCases(projectId, query)
    return { items: data, total: data.length, page: params.page, page_size: params.page_size }
  },
)

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  filterPriority.value = undefined
  filterModule.value = ''
  filterTitle.value = ''
  filterCaseType.value = undefined
  filterStatus.value = undefined
  filterReqId.value = undefined
  pagination.current = 1
  loadData()
}

// ── 新增/编辑/删除（useCRUD + FormModal）──
const defaultCaseForm = {
  title: '',
  module: '',
  req_id: undefined as number | undefined,
  priority: 'P1',
  case_type: 'functional',
  status: 'draft',
  preconditions: '',
  steps: [{ action: '', expected: '' }] as any[],
  expected_result: '',
}

const {
  modalVisible,
  modalLoading,
  editingId,
  formData,
  openCreate,
  openEdit,
  submit,
  handleDelete,
} = useCRUD<any>({
  api: {
    create: (data) => createCase(projectId, { ...data, req_id: data.req_id ?? null }),
    update: (id, data) => updateCase(projectId, id, { ...data, req_id: data.req_id ?? null }),
    remove: (id) => deleteCaseApi(projectId, id),
  },
  resourceName: '用例',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.title?.trim()) {
      message.warning('请输入用例名称')
      return false
    }
    return true
  },
})

function openCreateDialog() {
  openCreate({ ...defaultCaseForm, steps: [{ action: '', expected: '' }] })
}

function editCase(row: any) {
  openEdit(row.id, {
    title: row.title,
    module: row.module,
    req_id: row.req_id ?? undefined,
    priority: row.priority,
    case_type: row.case_type,
    status: row.status,
    preconditions: row.preconditions,
    steps: typeof row.steps === 'string' ? JSON.parse(row.steps || '[]') : (row.steps || []),
    expected_result: row.expected_result,
  })
}

function runCase(row: any) {
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

  router.push({
    path: `/projects/${projectId}/execution`,
    query: {
      caseId: row.id,
      caseTitle: row.title,
      instruction: encodeURIComponent(instruction),
    },
  })
}

const showGenerateModal = ref(false)
const generating = ref(false)
const selectedReqId = ref<number | null>(null)
const selectedLLMConfig = ref<number | null>(null)
const prompts = ref<Prompt[]>([])
const selectedPromptId = ref<number | null>(null)

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
  { title: '操作', key: 'action', width: 140, fixed: 'right' },
]

const priorityOptions = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

const caseTypeOptions = [
  { label: '功能测试', value: 'functional' },
  { label: '性能测试', value: 'performance' },
  { label: '安全测试', value: 'security' },
]

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '生效', value: 'active' },
  { label: '归档', value: 'archived' },
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

async function onReqChange(reqId: any) {
  featureModules.value = []
  selectedFeatureIds.value = []
  if (!reqId) return
  loadingFeatures.value = true
  try {
    const data = await getFeatures(projectId, Number(reqId))
    if (data.split_status === 'completed' || data.modules?.length > 0) {
      featureModules.value = data.modules || []
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
      prompt_id: selectedPromptId.value || undefined,
      backend: showCaseBackend.value ? caseBackend.value : undefined,
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
    setTimeout(() => loadData(), 5000)
  } catch (e: any) {
    message.error('提交生成任务失败：' + (e.message || '未知错误'))
  } finally {
    generating.value = false
  }
}

getRequirements(projectId).then(data => { requirements.value = data })
getLLMConfigs().then(data => { llmConfigs.value = data })
promptsApi.list('case_generation').then(data => { prompts.value = data }).catch(() => {})
fetchCaseBackend('case.generate', projectId).then(() => {
  caseBackend.value = caseDefaultBackend.value || 'local'
})
</script>

<style scoped>
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
