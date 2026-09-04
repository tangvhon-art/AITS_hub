<template>
  <div class="page-container">
    <PageHeader title="模型配置管理">
      <template #extra>
        <a-button type="primary" @click="openCreate(defaultForm)">
          <template #icon>
            <PlusOutlined />
          </template>
          新建模型配置
        </a-button>
      </template>
    </PageHeader>

    <a-alert
      message="支持四种接入模式：OpenAI兼容协议(DeepSeek/vLLM/TGI)、Anthropic Claude、本地Ollama"
      type="info"
      :show-icon="true"
      style="margin-bottom: 20px"
    />

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="配置名称">
          <a-input v-model:value="filters.name" placeholder="配置名称" allow-clear style="width: 180px" />
        </a-form-item>
        <a-form-item label="提供商">
          <a-select v-model:value="filters.provider" placeholder="提供商" allow-clear style="width: 180px" :options="providerOptions" />
        </a-form-item>
        <a-form-item label="模型名称">
          <a-input v-model:value="filters.model_name" placeholder="模型名称" allow-clear style="width: 160px" />
        </a-form-item>
        <a-form-item label="流式">
          <a-select v-model:value="filters.streaming" placeholder="流式" allow-clear style="width: 100px">
            <a-select-option :value="true">是</a-select-option>
            <a-select-option :value="false">否</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model:value="filters.priority" placeholder="优先级" :min="0" style="width: 100px" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filters.status" placeholder="状态" allow-clear style="width: 100px">
            <a-select-option value="active">启用</a-select-option>
            <a-select-option value="inactive">停用</a-select-option>
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
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.name)">删除</a-button>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 创建/编辑对话框 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑模型配置' : '新建模型配置'"
      :loading="modalLoading"
      width="640px"
      @ok="submit"
    >
      <a-form-item label="配置名称" required>
        <a-input v-model:value="formData.name" placeholder="例如：DeepSeek 官方" />
      </a-form-item>
      <a-form-item label="提供商" required>
        <a-select v-model:value="formData.provider" @change="onProviderChange" :options="providerOptions" />
      </a-form-item>
      <a-form-item v-if="formData.provider === 'openai_compatible'" label="API 格式">
        <a-select v-model:value="formData.api_format">
          <a-select-option value="chat_completions">Chat Completions（/v1/chat/completions）</a-select-option>
          <a-select-option value="responses">Responses API（/v1/responses）</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="formData.provider !== 'anthropic'" label="Base URL">
        <a-input v-model:value="formData.base_url" :placeholder="baseUrlPlaceholder" />
      </a-form-item>
      <a-form-item v-if="formData.provider !== 'ollama'" label="API Key">
        <a-input-password
          v-model:value="formData.api_key"
          placeholder="留空则不修改"
        />
      </a-form-item>
      <a-form-item label="模型名称" required>
        <a-input v-model:value="formData.model_name" :placeholder="modelNamePlaceholder" />
      </a-form-item>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="最大 Token">
            <a-input-number
              v-model:value="formData.max_tokens"
              :min="256"
              :max="128000"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="温度">
            <a-input-number
              v-model:value="formData.temperature"
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
            <a-input-number v-model:value="formData.priority" :min="0" style="width: 100%" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="流式输出">
            <a-switch v-model:checked="formData.streaming" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="设为默认">
            <a-switch v-model:checked="formData.is_default" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="描述">
        <a-textarea v-model:value="formData.description" :rows="2" placeholder="可选描述" />
      </a-form-item>
    </FormModal>

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
import { ref, reactive, computed } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getLLMConfigs, createLLMConfig, updateLLMConfig, deleteLLMConfig, testLLMConfig, setDefaultLLMConfig, type LLMConfigQuery } from '@/api/llm'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'

const filters = reactive<LLMConfigQuery>({
  name: undefined,
  provider: undefined,
  model_name: undefined,
  streaming: undefined,
  priority: undefined,
  status: undefined,
})

// ── 列表（后端返回全量，包装为 useList 统一形态）──
const { loading, list, total, pagination, loadData, handleTableChange } = useList<any>(
  async (params) => {
    const query: LLMConfigQuery = {}
    if (filters.name) query.name = filters.name
    if (filters.provider) query.provider = filters.provider
    if (filters.model_name) query.model_name = filters.model_name
    if (filters.streaming !== undefined && filters.streaming !== null) query.streaming = filters.streaming
    if (filters.priority !== undefined && filters.priority !== null) query.priority = filters.priority
    if (filters.status) query.status = filters.status
    const data = await getLLMConfigs(query)
    return { items: data, total: data.length, page: params.page, page_size: params.page_size }
  },
)

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  filters.name = undefined
  filters.provider = undefined
  filters.model_name = undefined
  filters.streaming = undefined
  filters.priority = undefined
  filters.status = undefined
  pagination.current = 1
  loadData()
}

// ── 新增/编辑/删除（useCRUD + FormModal）──
const defaultForm = {
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
  description: '',
  api_format: 'chat_completions',
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
    create: (data) => {
      const payload: any = { ...data }
      delete payload.api_key
      return createLLMConfig(payload)
    },
    update: (id, data) => {
      const payload: any = { ...data }
      if (!payload.api_key) delete payload.api_key
      return updateLLMConfig(id, payload)
    },
    remove: (id) => deleteLLMConfig(id),
  },
  resourceName: '模型配置',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.name?.trim()) {
      message.warning('请输入配置名称')
      return false
    }
    if (!formData.model_name?.trim()) {
      message.warning('请输入模型名称')
      return false
    }
    // 新建且非 ollama 时必须有 API Key
    if (editingId.value === null && !formData.api_key && formData.provider !== 'ollama') {
      message.warning('请输入 API Key')
      return false
    }
    return true
  },
})

/** 编辑：回填表单，API Key 留空 */
function editConfig(row: any) {
  openEdit(row.id, {
    ...row,
    api_key: '',
    api_format: row.api_format || 'chat_completions',
  })
}

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
  { title: '操作', key: 'action', width: 300, fixed: 'right' },
]

const providerOptions = [
  { label: 'OpenAI 兼容协议 (DeepSeek/vLLM/TGI)', value: 'openai_compatible' },
  { label: 'Anthropic Claude', value: 'anthropic' },
  { label: '本地 Ollama', value: 'ollama' },
]

const baseUrlPlaceholder = computed(() => {
  if (formData.provider === 'ollama') return 'http://localhost:11434'
  return 'https://api.deepseek.com/v1'
})

const modelNamePlaceholder = computed(() => {
  if (formData.provider === 'anthropic') return 'claude-3-5-sonnet-20241022'
  if (formData.provider === 'ollama') return 'llama3.1'
  return 'deepseek-chat'
})

function providerLabel(provider: string) {
  const map: Record<string, string> = {
    openai_compatible: 'OpenAI兼容',
    anthropic: 'Claude',
    ollama: 'Ollama',
  }
  return map[provider] || provider
}

function providerColor(provider: string) {
  const map: Record<string, string> = {
    openai_compatible: 'blue',
    anthropic: 'purple',
    ollama: 'green',
  }
  return map[provider] || 'default'
}

function onProviderChange() {
  if (formData.provider === 'ollama') {
    formData.base_url = 'http://localhost:11434'
    formData.api_key = ''
  } else if (formData.provider === 'openai_compatible') {
    formData.base_url = 'https://api.deepseek.com/v1'
  } else if (formData.provider === 'anthropic') {
    formData.base_url = ''
  }
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
  loadData()
}
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
