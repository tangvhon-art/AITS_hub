<template>
  <div class="page-container">
    <div class="page-header">
      <h2>需求管理</h2>
      <div class="header-actions">
        <a-button @click="showUploadModal = true" style="margin-right: 8px">
          <template #icon>
            <UploadOutlined />
          </template>
          上传文档
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
          <template v-if="column.key === 'source'">
            <a-tag :color="record.source === 'upload' ? 'green' : 'blue'">
              {{ record.source === 'upload' ? '上传' : '手动' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="generateCases(record)">生成用例</a-button>
            <a-button type="link" size="small" danger @click="deleteReq(record)">删除</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- 新建需求对话框 -->
    <a-modal
      v-model:open="showCreateModal"
      title="新建需求"
      @ok="saveRequirement"
      :confirm-loading="saving"
      width="600px"
    >
      <a-form layout="vertical">
        <a-form-item label="需求标题" required>
          <a-input v-model:value="reqForm.title" placeholder="请输入需求标题" />
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
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons-vue'
import { getRequirements, createRequirement, uploadRequirement as uploadRequirementApi, deleteRequirement, generateCases as generateCasesApi } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const requirements = ref<any[]>([])
const showCreateModal = ref(false)
const showUploadModal = ref(false)
const showGenerateModal = ref(false)
const uploadFile = ref<File | null>(null)
const generatingReq = ref<any>(null)
const generateCount = ref(10)
const selectedLLMConfig = ref<number | null>(null)
const llmConfigs = ref<any[]>([])

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '需求标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 160, fixed: 'right' }
]

const reqForm = reactive({
  title: '',
  content: ''
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

async function fetchRequirements() {
  loading.value = true
  try {
    requirements.value = await getRequirements(projectId)
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
    await createRequirement(projectId, reqForm)
    message.success('创建成功')
    showCreateModal.value = false
    reqForm.title = ''
    reqForm.content = ''
    fetchRequirements()
  } finally {
    saving.value = false
  }
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
      llm_config_id: selectedLLMConfig.value || undefined
    })
    message.success(`用例生成任务已提交（任务ID: ${result.task_id}），可在Agent任务中查看进度`)
    showGenerateModal.value = false
    // 更新需求状态为已生成
    fetchRequirements()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '提交失败，请重试')
  }
}

onMounted(() => {
  fetchRequirements()
  getLLMConfigs().then(data => { llmConfigs.value = data })
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
}
</style>
