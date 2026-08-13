<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型配置管理</h2>
      <a-button type="primary" @click="showCreateModal = true">
        <template #icon>
          <PlusOutlined />
        </template>
        新建模型配置
      </a-button>
    </div>

    <a-alert
      message="支持四种接入模式：OpenAI兼容协议(DeepSeek/vLLM/TGI)、Anthropic Claude、本地Ollama"
      type="info"
      :show-icon="true"
      style="margin-bottom: 20px"
    />

    <a-spin :spinning="loading">
      <a-table
        :columns="columns"
        :data-source="configs"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 1100 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span>{{ record.name }}</span>
            <a-tag v-if="record.is_default" color="success" style="margin-left: 8px">默认</a-tag>
          </template>
          <template v-else-if="column.key === 'provider'">
            <a-tag :color="providerColor(record.provider)">{{ providerLabel(record.provider) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'streaming'">
            <a-tag :color="record.streaming ? 'orange' : 'default'">
              {{ record.streaming ? '是' : '否' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'">
              {{ record.status === 'active' ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="testConfig(record)">测试连接</a-button>
            <a-button type="link" size="small" @click="editConfig(record)">编辑</a-button>
            <a-button v-if="!record.is_default" type="link" size="small" @click="setDefault(record)">设默认</a-button>
            <a-button type="link" size="small" danger @click="deleteConfig(record)">删除</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- 创建/编辑对话框 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingConfig ? '编辑模型配置' : '新建模型配置'"
      @ok="saveConfig"
      :confirm-loading="saving"
      width="640px"
    >
      <a-form layout="vertical">
        <a-form-item label="配置名称" required>
          <a-input v-model:value="configForm.name" placeholder="例如：DeepSeek 官方" />
        </a-form-item>
        <a-form-item label="提供商" required>
          <a-select v-model:value="configForm.provider" @change="onProviderChange" :options="providerOptions" />
        </a-form-item>
        <a-form-item v-if="configForm.provider !== 'anthropic'" label="Base URL">
          <a-input v-model:value="configForm.base_url" :placeholder="baseUrlPlaceholder" />
        </a-form-item>
        <a-form-item v-if="configForm.provider !== 'ollama'" label="API Key">
          <a-input-password
            v-model:value="configForm.api_key"
            placeholder="留空则不修改"
          />
        </a-form-item>
        <a-form-item label="模型名称" required>
          <a-input v-model:value="configForm.model_name" :placeholder="modelNamePlaceholder" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="最大 Token">
              <a-input-number
                v-model:value="configForm.max_tokens"
                :min="256"
                :max="128000"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="温度">
              <a-input-number
                v-model:value="configForm.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="优先级">
              <a-input-number v-model:value="configForm.priority" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="流式输出">
              <a-switch v-model:checked="configForm.streaming" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="设为默认">
              <a-switch v-model:checked="configForm.is_default" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="configForm.description" :rows="2" placeholder="可选描述" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 测试结果对话框 -->
    <a-modal
      v-model:open="showTestResult"
      title="连接测试结果"
      :footer="null"
      width="500px"
    >
      <div v-if="testLoading" style="text-align: center; padding: 20px">
        <a-spin size="large" />
        <p style="margin-top: 12px; color: rgba(0, 0, 0, 0.45)">正在测试连接...</p>
      </div>
      <div v-else>
        <a-alert
          :message="testResult.status === 'success' ? '连接成功' : '连接失败'"
          :type="testResult.status === 'success' ? 'success' : 'error'"
          :show-icon="true"
        />
        <div v-if="testResult.response" style="margin-top: 16px">
          <p style="font-weight: 500; margin-bottom: 8px">模型回复：</p>
          <div class="response-box">{{ testResult.response }}</div>
        </div>
        <div v-if="testResult.error" style="margin-top: 16px">
          <p style="font-weight: 500; margin-bottom: 8px">错误信息：</p>
          <p style="color: #ff4d4f; word-break: break-all; margin: 0">{{ testResult.error }}</p>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getLLMConfigs, createLLMConfig, updateLLMConfig, deleteLLMConfig, testLLMConfig, setDefaultLLMConfig } from '@/api/llm'

const loading = ref(false)
const saving = ref(false)
const configs = ref<any[]>([])
const showCreateModal = ref(false)
const editingConfig = ref<any>(null)

const configForm = reactive({
  name: '',
  provider: 'openai_compatible',
  base_url: '',
  api_key: '',
  model_name: '',
  max_tokens: 4096,
  temperature: 0.7,
  streaming: false,
  is_default: false,
  status: 'active',
  priority: 0,
  description: ''
})

const showTestResult = ref(false)
const testLoading = ref(false)
const testResult = ref<any>({})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '配置名称', dataIndex: 'name', key: 'name', width: 160 },
  { title: '提供商', dataIndex: 'provider', key: 'provider', width: 120 },
  { title: '模型名称', dataIndex: 'model_name', key: 'model_name', width: 160 },
  { title: 'Base URL', dataIndex: 'base_url', key: 'base_url', ellipsis: true },
  { title: '流式', dataIndex: 'streaming', key: 'streaming', width: 70 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 260, fixed: 'right' }
]

const providerOptions = [
  { label: 'OpenAI 兼容协议 (DeepSeek/vLLM/TGI)', value: 'openai_compatible' },
  { label: 'Anthropic Claude', value: 'anthropic' },
  { label: '本地 Ollama', value: 'ollama' }
]

const baseUrlPlaceholder = computed(() => {
  if (configForm.provider === 'ollama') return 'http://localhost:11434'
  return 'https://api.deepseek.com/v1'
})

const modelNamePlaceholder = computed(() => {
  if (configForm.provider === 'anthropic') return 'claude-3-5-sonnet-20241022'
  if (configForm.provider === 'ollama') return 'llama3.1'
  return 'deepseek-chat'
})

function providerLabel(provider: string) {
  const map: Record<string, string> = {
    openai_compatible: 'OpenAI兼容',
    anthropic: 'Claude',
    ollama: 'Ollama'
  }
  return map[provider] || provider
}

function providerColor(provider: string) {
  const map: Record<string, string> = {
    openai_compatible: 'blue',
    anthropic: 'purple',
    ollama: 'green'
  }
  return map[provider] || 'default'
}

function onProviderChange() {
  if (configForm.provider === 'ollama') {
    configForm.base_url = 'http://localhost:11434'
    configForm.api_key = ''
  } else if (configForm.provider === 'openai_compatible') {
    configForm.base_url = 'https://api.deepseek.com/v1'
  } else if (configForm.provider === 'anthropic') {
    configForm.base_url = ''
  }
}

async function fetchConfigs() {
  loading.value = true
  try {
    configs.value = await getLLMConfigs()
  } finally {
    loading.value = false
  }
}

function editConfig(row: any) {
  editingConfig.value = row
  Object.assign(configForm, {
    name: row.name,
    provider: row.provider,
    base_url: row.base_url,
    api_key: '',
    model_name: row.model_name,
    max_tokens: row.max_tokens,
    temperature: row.temperature,
    streaming: row.streaming || false,
    is_default: row.is_default,
    status: row.status,
    priority: row.priority,
    description: row.description
  })
  showCreateModal.value = true
}

async function saveConfig() {
  if (!configForm.name.trim()) {
    message.warning('请输入配置名称')
    return
  }
  if (!configForm.model_name.trim()) {
    message.warning('请输入模型名称')
    return
  }

  const data: any = { ...configForm }
  if (!data.api_key) delete data.api_key

  saving.value = true
  try {
    if (editingConfig.value) {
      await updateLLMConfig(editingConfig.value.id, data)
      message.success('更新成功')
    } else {
      if (!configForm.api_key && configForm.provider !== 'ollama') {
        message.warning('请输入 API Key')
        return
      }
      await createLLMConfig(configForm)
      message.success('创建成功')
    }
    showCreateModal.value = false
    editingConfig.value = null
    fetchConfigs()
  } finally {
    saving.value = false
  }
}

function deleteConfig(row: any) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除配置「${row.name}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteLLMConfig(row.id)
      message.success('删除成功')
      fetchConfigs()
    }
  })
}

async function testConfig(row: any) {
  showTestResult.value = true
  testLoading.value = true
  testResult.value = {}
  try {
    testResult.value = await testLLMConfig(row.id)
  } catch (e: any) {
    testResult.value = { status: 'failed', error: e.message }
  } finally {
    testLoading.value = false
  }
}

async function setDefault(row: any) {
  await setDefaultLLMConfig(row.id)
  message.success('已设为默认模型')
  fetchConfigs()
}

onMounted(fetchConfigs)
</script>

<style scoped>
.response-box {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(0, 0, 0, 0.88);
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>
