<template>
  <div class="page-container">
    <div class="page-header">
      <h2>需求管理</h2>
      <div class="header-actions">
        <a-select
          v-model:value="filterVersionId"
          placeholder="全部版本"
          allow-clear
          style="width: 150px; margin-right: 8px"
          @change="fetchRequirements"
        >
          <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
        </a-select>
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
        <a-button type="primary" @click="showCreateModal = true">
          <template #icon>
            <PlusOutlined />
          </template>
          新建需求
        </a-button>
      </div>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :columns="columns"
        :data-source="requirements"
        :pagination="false"
        row-key="id"
        size="middle"
      >
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
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="editRequirement(record)">编辑</a-button>
            <a-button type="link" size="small" @click="generateCases(record)">生成用例</a-button>
            <a-button type="link" size="small" danger @click="deleteReq(record)">删除</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- 新建/编辑需求对话框 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingId ? '编辑需求' : '新建需求'"
      @ok="saveRequirement"
      @cancel="resetForm"
      :confirm-loading="saving"
      width="600px"
    >
      <a-form layout="vertical">
        <a-form-item label="需求标题" required>
          <a-input v-model:value="reqForm.title" placeholder="请输入需求标题" />
        </a-form-item>
        <a-form-item label="所属版本">
          <a-select v-model:value="reqForm.version_id" placeholder="选择版本（可选）" allow-clear>
            <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="需求状态">
          <a-select v-model:value="reqForm.status" placeholder="选择状态">
            <a-select-option value="pending">待生成</a-select-option>
            <a-select-option value="generated">已生成</a-select-option>
            <a-select-option value="reviewed">已评审</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="需求内容">
          <a-textarea
            v-model:value="reqForm.content"
            :rows="8"
            placeholder="请输入需求详细描述"
          />
        </a-form-item>
      </a-form>
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

    <!-- 生成用例对话框 -->
    <a-modal
      v-model:open="showGenerateModal"
      title="AI 生成测试用例"
      @ok="doGenerate"
    >
      <a-form layout="vertical">
        <a-form-item label="需求">
          <span>{{ generatingReq?.title }}</span>
        </a-form-item>
        <a-form-item label="生成数量">
          <a-input-number v-model:value="generateCount" :min="1" :max="50" style="width: 100%" />
        </a-form-item>
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="selectedCasePrompt"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="casePrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
        <a-form-item label="模型配置">
          <a-select
            v-model:value="selectedLLMConfig"
            placeholder="使用默认模型"
            allow-clear
            :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
          />
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
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, InboxOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { getRequirements, createRequirement, updateRequirement, uploadRequirement as uploadRequirementApi, deleteRequirement, generateCases as generateCasesApi, generateRequirement as generateRequirementApi, generateRequirementStatus } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'
import { promptsApi, type Prompt } from '@/api/prompts'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const requirements = ref<any[]>([])
const showCreateModal = ref(false)
const showUploadModal = ref(false)
const showGenerateModal = ref(false)
const showAiGenerateModal = ref(false)
const aiGenerating = ref(false)
const uploadFile = ref<File | null>(null)
const generatingReq = ref<any>(null)
const generateCount = ref(10)
const selectedLLMConfig = ref<number | null>(null)
const selectedCasePrompt = ref<number | null>(null)
const llmConfigs = ref<any[]>([])
const casePrompts = ref<Prompt[]>([])
const requirementPrompts = ref<Prompt[]>([])
const versions = ref<ProjectVersion[]>([])
const filterVersionId = ref<number | undefined>(undefined)
const editingId = ref<number | null>(null)

const aiGenForm = reactive({
  description: '',
  version_id: undefined as number | undefined,
  prompt_id: undefined as number | undefined,
  llm_config_id: undefined as number | undefined
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '需求标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '所属版本', dataIndex: 'version_id', key: 'version', width: 120 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 220, fixed: 'right' }
]

function getVersionName(versionId?: number | null) {
  if (!versionId) return '-'
  return versions.value.find(v => v.id === versionId)?.name || '-'
}

const reqForm = reactive({
  title: '',
  content: '',
  version_id: undefined as number | undefined,
  status: 'pending' as string
})

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'default',
    generated: 'processing',
    reviewed: 'success'
  }
  return map[status] || 'default'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待生成',
    generated: '已生成',
    reviewed: '已评审'
  }
  return map[status] || status
}

function sourceColor(source: string) {
  const map: Record<string, string> = {
    manual: 'blue',
    upload: 'green',
    ai: 'purple'
  }
  return map[source] || 'default'
}

function sourceLabel(source: string) {
  const map: Record<string, string> = {
    manual: '手动',
    upload: '上传',
    ai: 'AI生成'
  }
  return map[source] || source
}

async function fetchRequirements() {
  loading.value = true
  try {
    requirements.value = await getRequirements(projectId, { version_id: filterVersionId.value })
  } finally {
    loading.value = false
  }
}

async function saveRequirement() {
  if (!reqForm.title.trim()) {
    message.warning('请输入需求标题')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateRequirement(projectId, editingId.value, {
        title: reqForm.title,
        content: reqForm.content,
        version_id: reqForm.version_id,
        status: reqForm.status
      })
      message.success('更新成功')
    } else {
      await createRequirement(projectId, { title: reqForm.title, content: reqForm.content, version_id: reqForm.version_id })
      message.success('创建成功')
    }
    showCreateModal.value = false
    resetForm()
    fetchRequirements()
  } finally {
    saving.value = false
  }
}

function resetForm() {
  editingId.value = null
  reqForm.title = ''
  reqForm.content = ''
  reqForm.version_id = undefined
  reqForm.status = 'pending'
}

function editRequirement(row: any) {
  editingId.value = row.id
  reqForm.title = row.title
  reqForm.content = row.content || ''
  reqForm.version_id = row.version_id
  reqForm.status = row.status || 'pending'
  showCreateModal.value = true
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
    fetchRequirements()
  } finally {
    uploading.value = false
  }
}

function deleteReq(row: any) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除需求「${row.title}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteRequirement(projectId, row.id)
      message.success('删除成功')
      fetchRequirements()
    }
  })
}

function generateCases(row: any) {
  generatingReq.value = row
  showGenerateModal.value = true
}

async function doGenerate() {
  try {
    const result: any = await generateCasesApi(projectId, {
      requirement_id: generatingReq.value.id,
      content: generatingReq.value.content,
      count: generateCount.value,
      llm_config_id: selectedLLMConfig.value || undefined,
      prompt_id: selectedCasePrompt.value || undefined
    })
    message.success(`用例生成任务已提交（任务ID: ${result.task_id}），可在Agent任务中查看进度`)
    showGenerateModal.value = false
    selectedCasePrompt.value = null
    fetchRequirements()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '提交失败，请重试')
  }
}

async function doAiGenerate() {
  if (!aiGenForm.description.trim()) {
    message.warning('请输入需求描述')
    return
  }
  aiGenerating.value = true
  try {
    const result: any = await generateRequirementApi(projectId, {
      description: aiGenForm.description,
      llm_config_id: aiGenForm.llm_config_id || undefined,
      prompt_id: aiGenForm.prompt_id || undefined,
      version_id: aiGenForm.version_id || undefined
    })
    message.success(`需求生成任务已提交（任务ID: ${result.task_id}），可在Agent任务中查看进度`)
    showAiGenerateModal.value = false
    aiGenForm.description = ''
    aiGenForm.version_id = undefined
    aiGenForm.prompt_id = undefined
    aiGenForm.llm_config_id = undefined
    setTimeout(() => fetchRequirements(), 3000)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '提交失败，请重试')
  } finally {
    aiGenerating.value = false
  }
}

onMounted(() => {
  fetchRequirements()
  getLLMConfigs().then(data => { llmConfigs.value = data })
  getVersions(projectId, { page_size: 200 }).then(data => { versions.value = data.items }).catch(() => {})
  promptsApi.list('case_generation').then(data => { casePrompts.value = data }).catch(() => {})
  promptsApi.list('requirement_generation').then(data => { requirementPrompts.value = data }).catch(() => {})
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
}
</style>
