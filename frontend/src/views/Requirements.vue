<template>
  <div class="page-container">
    <PageHeader title="需求管理">
      <template #extra>
        <a-button @click="showUploadModal = true" style="margin-right: 8px">
          <template #icon>
            <UploadOutlined />
          </template>
          上传文档
        </a-button>
        <a-button @click="showAiGenerateModal = true" style="margin-right: 8px">
          <template #icon>
            <RobotOutlined />
          </template>
          AI生成需求
        </a-button>
        <a-button @click="syncAllToKnowledge" :loading="syncingKb" style="margin-right: 8px">
          <template #icon>
            <CloudUploadOutlined />
          </template>
          同步到知识库
        </a-button>
        <a-button type="primary" @click="openCreate()">
          <template #icon>
            <PlusOutlined />
          </template>
          新建需求
        </a-button>
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="需求标题">
          <a-input v-model:value="filterTitle" placeholder="需求标题" allow-clear style="width: 180px" />
        </a-form-item>
        <a-form-item label="来源">
          <a-select v-model:value="filterSource" placeholder="来源" allow-clear style="width: 120px">
            <a-select-option value="manual">手动</a-select-option>
            <a-select-option value="upload">上传</a-select-option>
            <a-select-option value="ai">AI生成</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px">
            <a-select-option value="pending">待生成</a-select-option>
            <a-select-option value="generated">已生成</a-select-option>
            <a-select-option value="reviewed">已评审</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="所属版本">
          <a-select v-model:value="filterVersionId" placeholder="全部版本" allow-clear style="width: 150px">
            <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </SearchBar>

    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      size="middle"
      @change="handleTableChange"
    >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'version'">
          <a-tag v-if="record.version_id" color="blue">{{ getVersionName(record.version_id) }}</a-tag>
          <span v-else style="color: #999">-</span>
        </template>
        <template v-else-if="column.key === 'source'">
          <a-tag :color="sourceColor(record.source)">{{ sourceLabel(record.source) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'feature_status'">
          <a-tooltip v-if="record.feature_split_status === 'failed'" title="拆分失败，点击重新拆分">
            <a-tag color="red" style="cursor: pointer" @click.stop="resplitFeatures(record)">拆分失败</a-tag>
          </a-tooltip>
          <a-tag v-else-if="record.feature_split_status === 'splitting'" color="processing">拆分中</a-tag>
          <a-tag v-else-if="record.feature_split_status === 'split'" color="green">已拆分</a-tag>
          <a-tooltip v-else title="点击立即拆分功能点">
            <a-tag color="orange" style="cursor: pointer" @click.stop="resplitFeatures(record)">待拆分</a-tag>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="viewRequirement(record)"><EyeOutlined /> 查看</a-button>
          <a-button type="link" size="small" @click="editRequirement(record)">编辑</a-button>
          <a-button type="link" size="small" @click="generateCases(record)">生成用例</a-button>
          <a-button type="link" size="small" @click="syncOneToKnowledge(record)">同步知识库</a-button>
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.title)">删除</a-button>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 新建/编辑需求对话框 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑需求' : '新建需求'"
      :loading="modalLoading"
      width="600px"
      @ok="submit"
      @cancel="closeModal"
    >
      <a-form-item label="需求标题" required>
        <a-input v-model:value="formData.title" placeholder="请输入需求标题" />
      </a-form-item>
      <a-form-item label="所属版本">
        <a-select v-model:value="formData.version_id" placeholder="选择版本（可选）" allow-clear>
          <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="需求状态">
        <a-select v-model:value="formData.status" placeholder="选择状态">
          <a-select-option value="pending">待生成</a-select-option>
          <a-select-option value="generated">已生成</a-select-option>
          <a-select-option value="reviewed">已评审</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="需求内容">
        <a-textarea
          v-model:value="formData.content"
          :rows="8"
          placeholder="请输入需求详细描述"
        />
      </a-form-item>
    </FormModal>

    <!-- 查看需求弹窗（Markdown 渲染） -->
    <a-modal v-model:open="showViewModal" title="需求详情" :footer="null" width="800px">
      <div v-if="viewingReq" class="req-detail">
        <a-descriptions :column="2" size="small" bordered style="margin-bottom: 16px">
          <a-descriptions-item label="需求标题">{{ viewingReq.title }}</a-descriptions-item>
          <a-descriptions-item label="所属版本">{{ getVersionName(viewingReq.version_id) }}</a-descriptions-item>
          <a-descriptions-item label="来源">
            <a-tag :color="sourceColor(viewingReq.source)">{{ sourceLabel(viewingReq.source) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(viewingReq.status)">{{ statusLabel(viewingReq.status) }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>
        <MdView :content="viewingReq?.content" />
      </div>
    </a-modal>

    <!-- 上传文档对话框 -->
    <a-modal
      v-model:open="showUploadModal"
      title="上传需求文档"
      @ok="uploadRequirement"
      :confirm-loading="uploading"
      :ok-button-props="{ disabled: !uploadFile }"
    >
      <a-upload
        drag
        :auto-upload="false"
        :max-count="1"
        accept=".docx,.pdf,.txt,.md"
        @change="handleFileChange"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined :style="{ fontSize: '48px', color: '#1677ff' }" />
        </p>
        <p class="ant-upload-text">将文件拖到此处，或<span style="color: #1677ff">点击上传</span></p>
        <p class="ant-upload-hint">支持 .docx / .pdf / .txt / .md 格式</p>
      </a-upload>
    </a-modal>

    <!-- 生成用例对话框（功能点选择） -->
    <FeatureSelectModal
      v-model:open="showGenerateModal"
      :project-id="projectId"
      :requirement="generatingReq"
      @success="onCaseGenerateSuccess"
    />

    <!-- 重新拆分功能点弹窗 -->
    <a-modal
      v-model:open="showResplitModal"
      title="重新拆分功能点"
      @ok="doResplit"
      :confirm-loading="resplitting"
      width="520px"
    >
      <div v-if="resplittingReq" style="margin-bottom: 16px; padding: 8px 12px; background: #f5f7fa; border-radius: 6px;">
        <span style="color: #606266;">需求：</span>
        <span style="font-weight: 500;">{{ resplittingReq.title }}</span>
      </div>
      <a-form layout="vertical">
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="resplitForm.prompt_id"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="splitPrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
        <a-form-item label="模型配置">
          <a-select
            v-model:value="resplitForm.llm_config_id"
            placeholder="使用默认模型"
            allow-clear
            :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
          />
        </a-form-item>
        <a-form-item v-if="showSplitBackend" label="执行方式">
          <a-radio-group v-model:value="splitBackend" :options="AI_BACKEND_OPTIONS" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- AI生成需求对话框 -->
    <a-modal
      v-model:open="showAiGenerateModal"
      title="AI 生成需求文档"
      @ok="doAiGenerate"
      :confirm-loading="aiGenerating"
      width="600px"
    >
      <a-form layout="vertical">
        <a-form-item label="需求描述" required>
          <a-textarea
            v-model:value="aiGenForm.description"
            :rows="6"
            placeholder="请输入需求的简要描述，AI 将自动生成结构化的需求文档..."
          />
        </a-form-item>
        <a-form-item label="所属版本">
          <a-select v-model:value="aiGenForm.version_id" placeholder="选择版本（可选）" allow-clear>
            <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="aiGenForm.prompt_id"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="requirementPrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
        <a-form-item label="模型配置">
          <a-select
            v-model:value="aiGenForm.llm_config_id"
            placeholder="使用默认模型"
            allow-clear
            :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
          />
        </a-form-item>
        <a-form-item v-if="showReqBackend" label="执行方式">
          <a-radio-group v-model:value="reqBackend" :options="AI_BACKEND_OPTIONS" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, InboxOutlined, RobotOutlined, CloudUploadOutlined, EyeOutlined } from '@ant-design/icons-vue'
import { getRequirements, createRequirement, updateRequirement, uploadRequirement as uploadRequirementApi, deleteRequirement, generateRequirement as generateRequirementApi, splitFeatures as splitFeaturesApi } from '@/api/cases'
import { syncRequirementsToKnowledge } from '@/api/knowledge'
import { getLLMConfigs } from '@/api/llm'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'
import { promptsApi, type Prompt } from '@/api/prompts'
import MdView from '@/components/MdView.vue'
import FeatureSelectModal from '@/components/FeatureSelectModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'
import { useWorkflowBackend } from '@/composables/useWorkflowBackend'
import { AI_BACKEND_OPTIONS } from '@/constants/enums'

const { showBackendOption: showReqBackend, defaultBackend: reqDefaultBackend, fetch: fetchReqBackend } = useWorkflowBackend()
const reqBackend = ref('local')

const {
  showBackendOption: showSplitBackend,
  defaultBackend: splitDefaultBackend,
  fetch: fetchSplitBackend,
} = useWorkflowBackend()
const splitBackend = ref('local')

const route = useRoute()
const projectId = Number(route.params.id)

const uploading = ref(false)
const syncingKb = ref(false)
const showUploadModal = ref(false)
const showViewModal = ref(false)
const viewingReq = ref<any>(null)
const showGenerateModal = ref(false)
const showAiGenerateModal = ref(false)
const showResplitModal = ref(false)
const aiGenerating = ref(false)
const resplitting = ref(false)
const uploadFile = ref<File | null>(null)
const generatingReq = ref<any>(null)
const resplittingReq = ref<any>(null)
const llmConfigs = ref<any[]>([])
const requirementPrompts = ref<Prompt[]>([])
const splitPrompts = ref<Prompt[]>([])
const versions = ref<ProjectVersion[]>([])
const filterVersionId = ref<number | undefined>(undefined)
const filterTitle = ref('')
const filterSource = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)

// ── 列表（后端返回全量，包装为 useList 统一形态）──
const { loading, list, total, pagination, loadData, handleTableChange } = useList<any>(
  async (params) => {
    const query: any = {}
    if (filterVersionId.value) query.version_id = filterVersionId.value
    if (filterTitle.value) query.title = filterTitle.value
    if (filterSource.value) query.source = filterSource.value
    if (filterStatus.value) query.status = filterStatus.value
    const data = await getRequirements(projectId, query)
    return { items: data, total: data.length, page: params.page, page_size: params.page_size }
  },
)

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  filterVersionId.value = undefined
  filterTitle.value = ''
  filterSource.value = undefined
  filterStatus.value = undefined
  pagination.current = 1
  loadData()
}

// ── 新增/编辑/删除（useCRUD + FormModal）──
const defaultReqForm = {
  title: '',
  content: '',
  version_id: undefined as number | undefined,
  status: 'pending' as string,
}

const {
  modalVisible,
  modalLoading,
  editingId,
  formData,
  openCreate,
  openEdit,
  closeModal,
  submit,
  handleDelete,
} = useCRUD<any>({
  api: {
    create: (data) => createRequirement(projectId, { title: data.title, content: data.content, version_id: data.version_id }),
    update: (id, data) => updateRequirement(projectId, id, { title: data.title, content: data.content, version_id: data.version_id, status: data.status }),
    remove: (id) => deleteRequirement(projectId, id),
  },
  resourceName: '需求',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.title?.trim()) {
      message.warning('请输入需求标题')
      return false
    }
    return true
  },
})

function editRequirement(row: any) {
  openEdit(row.id, {
    title: row.title,
    content: row.content || '',
    version_id: row.version_id,
    status: row.status || 'pending',
  })
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '需求标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '所属版本', dataIndex: 'version_id', key: 'version', width: 120 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '功能点', dataIndex: 'feature_split_status', key: 'feature_status', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 380, fixed: 'right' },
]

function getVersionName(versionId?: number | null) {
  if (!versionId) return '-'
  return versions.value.find(v => v.id === versionId)?.name || '-'
}

function statusColor(status: string) {
  const map: Record<string, string> = { pending: 'default', generated: 'processing', reviewed: 'success' }
  return map[status] || 'default'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '待生成', generated: '已生成', reviewed: '已评审' }
  return map[status] || status
}

function sourceColor(source: string) {
  const map: Record<string, string> = { manual: 'blue', upload: 'green', ai: 'purple' }
  return map[source] || 'default'
}

function sourceLabel(source: string) {
  const map: Record<string, string> = { manual: '手动', upload: '上传', ai: 'AI生成' }
  return map[source] || source
}

function viewRequirement(row: any) {
  viewingReq.value = row
  showViewModal.value = true
}

function handleFileChange(info: any) {
  if (info.fileList.length > 0) {
    uploadFile.value = info.fileList[0].originFileObj
  } else {
    uploadFile.value = null
  }
}

async function uploadRequirement() {
  if (!uploadFile.value) return
  uploading.value = true
  try {
    await uploadRequirementApi(projectId, uploadFile.value)
    message.success('上传成功')
    showUploadModal.value = false
    uploadFile.value = null
    loadData()
  } finally {
    uploading.value = false
  }
}

async function syncAllToKnowledge() {
  syncingKb.value = true
  try {
    const res = await syncRequirementsToKnowledge(projectId)
    message.success(res.message || `已同步 ${res.synced} 条需求到知识库`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '同步失败')
  } finally {
    syncingKb.value = false
  }
}

async function syncOneToKnowledge(row: any) {
  try {
    const res = await syncRequirementsToKnowledge(projectId, [row.id])
    message.success(res.message || '同步成功，正在生成向量切片')
  } catch (e: any) {
    message.error(e.response?.data?.detail || '同步失败')
  }
}

function generateCases(row: any) {
  generatingReq.value = row
  showGenerateModal.value = true
}

function onCaseGenerateSuccess() {
  loadData()
}

function resplitFeatures(row: any) {
  resplittingReq.value = row
  resplitForm.prompt_id = undefined
  resplitForm.llm_config_id = undefined
  splitBackend.value = splitDefaultBackend.value || 'local'
  showResplitModal.value = true
}

const resplitForm = reactive({
  prompt_id: undefined as number | undefined,
  llm_config_id: undefined as number | undefined,
})

async function doResplit() {
  if (!resplittingReq.value) return
  resplitting.value = true
  try {
    await splitFeaturesApi(projectId, resplittingReq.value.id, {
      llm_config_id: resplitForm.llm_config_id || undefined,
      backend: showSplitBackend.value ? splitBackend.value : undefined,
    })
    message.success('功能点拆分任务已提交')
    resplittingReq.value.feature_split_status = 'splitting'
    showResplitModal.value = false
    setTimeout(() => loadData(), 5000)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '拆分失败')
  } finally {
    resplitting.value = false
  }
}

const aiGenForm = reactive({
  description: '',
  version_id: undefined as number | undefined,
  prompt_id: undefined as number | undefined,
  llm_config_id: undefined as number | undefined,
})

async function doAiGenerate() {
  if (!aiGenForm.description.trim()) {
    message.warning('请输入需求描述')
    return
  }
  aiGenerating.value = true
  try {
    await generateRequirementApi(projectId, {
      description: aiGenForm.description,
      version_id: aiGenForm.version_id,
      llm_config_id: aiGenForm.llm_config_id || undefined,
      prompt_id: aiGenForm.prompt_id || undefined,
      backend: showReqBackend.value ? reqBackend.value : undefined,
    })
    message.success('需求生成任务已提交')
    showAiGenerateModal.value = false
    aiGenForm.description = ''
    setTimeout(() => loadData(), 5000)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '生成失败')
  } finally {
    aiGenerating.value = false
  }
}

getVersions(projectId).then(data => { versions.value = ((data as any).items ?? data) as ProjectVersion[] })
getLLMConfigs().then(data => { llmConfigs.value = data })
promptsApi.list('requirement_generation').then(data => { requirementPrompts.value = data }).catch(() => {})
promptsApi.list('feature_split').then(data => { splitPrompts.value = data }).catch(() => {})
fetchReqBackend('requirement.generate', projectId).then(() => {
  reqBackend.value = reqDefaultBackend.value || 'local'
})
fetchSplitBackend('requirement.split_features', projectId).then(() => {
  splitBackend.value = splitDefaultBackend.value || 'local'
})
</script>

<style scoped>
.req-detail { line-height: 1.6; }
</style>
