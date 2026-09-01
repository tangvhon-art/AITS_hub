<template>
  <div class="workflow-config-page">
    <div class="page-header">
      <h2>外部工作流平台接入</h2>
      <a-tag color="purple">系统级配置</a-tag>
    </div>

    <a-alert
      message="配置外部工作流平台接入：平台连接（凭证加密）→ Webhook 全局开关 → 模块后端配置。业务页面提交时可选择 local/workflow 执行后端。"
      type="info"
      :show-icon="true"
      style="margin-bottom: 16px"
    />

    <a-tabs v-model:activeKey="activeTab" type="card">
      <!-- ════════ Tab 1：平台连接 ════════ -->
      <a-tab-pane key="connectors" tab="平台连接">
        <div class="tab-toolbar">
          <a-button type="primary" @click="openConnectorModal()">
            <template #icon><PlusOutlined /></template>
            新建连接
          </a-button>
        </div>
        <a-table
          :columns="connectorColumns"
          :data-source="connectors"
          :loading="connectorsLoading"
          row-key="id"
          size="middle"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'platform_type'">
              <a-tag :color="WORKFLOW_PLATFORM_COLOR[record.platform_type] || 'default'">
                {{ WORKFLOW_PLATFORM_TEXT[record.platform_type] || record.platform_type }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'active' ? 'green' : 'default'">
                {{ record.status === 'active' ? '启用' : '停用' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'auth_token_masked'">
              <span class="mono">{{ record.auth_token_masked || '-' }}</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" size="small" @click="openConnectorModal(record)">编辑</a-button>
              <a-button type="link" size="small" danger @click="deleteConnector(record)">删除</a-button>
            </template>
          </template>
        </a-table>

        <!-- 连接表单抽屉 -->
        <a-drawer
          v-model:open="connectorModalVisible"
          :title="connectorEditing ? '编辑平台连接' : '新建平台连接'"
          width="520"
          :footer="null"
        >
          <a-form layout="vertical">
            <a-form-item label="连接名称" required>
              <a-input v-model:value="connectorForm.name" placeholder="例如：Coze 官方" />
            </a-form-item>
            <a-form-item label="平台类型" required>
              <a-select v-model:value="connectorForm.platform_type" :options="WORKFLOW_PLATFORM_OPTIONS" />
            </a-form-item>
            <a-form-item label="服务地址（Base URL）" required>
              <a-input v-model:value="connectorForm.base_url" placeholder="https://api.coze.cn" />
            </a-form-item>
            <a-form-item label="调用路径">
              <a-input v-model:value="connectorForm.run_path" placeholder="/v1/workflows/run" />
            </a-form-item>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="鉴权方式">
                  <a-select v-model:value="connectorForm.auth_type">
                    <a-select-option value="bearer">Bearer Token</a-select-option>
                    <a-select-option value="apikey">API Key</a-select-option>
                    <a-select-option value="custom">自定义</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="鉴权 Header 名">
                  <a-input v-model:value="connectorForm.auth_header" placeholder="Authorization" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="凭证 Token（留空则不修改）">
              <a-input-password v-model:value="connectorForm.auth_token" placeholder="填写明文，保存时加密存储" />
            </a-form-item>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="受理超时（秒）">
                  <a-input-number v-model:value="connectorForm.accept_timeout" :min="5" :max="600" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="状态">
                  <a-select v-model:value="connectorForm.status">
                    <a-select-option value="active">启用</a-select-option>
                    <a-select-option value="inactive">停用</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>

          <template #extra>
            <div class="drawer-footer">
              <a-button @click="connectorModalVisible = false">取消</a-button>
              <a-button type="primary" :loading="connectorSaving" @click="saveConnector">保存</a-button>
            </div>
          </template>
        </a-drawer>
      </a-tab-pane>

      <!-- ════════ Tab 2：Webhook 配置 ════════ -->
      <a-tab-pane key="webhook" tab="Webhook 配置">
        <a-spin :spinning="webhookLoading">
          <a-form layout="vertical" style="max-width: 560px">
            <a-form-item label="全局开关">
              <a-switch
                v-model:checked="webhookForm.enabled"
                checked-children="启用"
                un-checked-children="关闭"
              />
              <span class="hint">关闭后所有模块强制使用本地执行</span>
            </a-form-item>
            <a-form-item label="Webhook 接收地址（固定端点）">
              <a-input v-model:value="webhookForm.webhook_url" placeholder="/api/workflow/webhook" />
              <span class="hint">外部平台回调此地址，AITS 通过 uuid 定位任务</span>
            </a-form-item>
            <a-form-item label="回调超时（秒）">
              <a-input-number v-model:value="webhookForm.callback_timeout" :min="60" :max="86400" style="width: 100%" />
              <span class="hint">超过此时间未收到回调，自动降级本地执行</span>
            </a-form-item>
            <a-form-item label="签名密钥（HMAC-SHA256）">
              <a-input-group compact>
                <a-input
                  :value="secretVisible ? (webhookConfig?.secret_plain || '(未生成)') : (webhookConfig?.secret_masked || '(未生成)')"
                  style="width: calc(100% - 250px)"
                  readonly
                  class="mono"
                />
                <a-button @click="toggleSecretVisible" :title="secretVisible ? '隐藏密钥' : '显示密钥'">
                  <component :is="secretVisible ? EyeInvisibleOutlined : EyeOutlined" />
                </a-button>
                <a-button @click="copySecret" :disabled="!webhookConfig?.secret_plain" title="复制完整密钥">
                  <template #icon><CopyOutlined /></template>
                  复制
                </a-button>
                <a-button type="primary" @click="regenerateSecret" style="width: 110px">
                  重新生成
                </a-button>
              </a-input-group>
              <span class="hint">回调请求需在 X-Aits-Signature 头携带 HMAC-SHA256 签名</span>
            </a-form-item>
            <a-form-item>
              <a-button type="primary" :loading="webhookSaving" @click="saveWebhook">保存配置</a-button>
            </a-form-item>
          </a-form>
        </a-spin>
      </a-tab-pane>

      <!-- ════════ Tab 3：模块后端配置 ════════ -->
      <a-tab-pane key="modules" tab="模块后端">
        <div class="tab-toolbar">
          <a-button type="primary" @click="openModuleModal()">
            <template #icon><PlusOutlined /></template>
            配置模块后端
          </a-button>
        </div>
        <a-table
          :columns="moduleColumns"
          :data-source="moduleConfigs"
          :loading="modulesLoading"
          row-key="id"
          size="middle"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'module_id'">
              <a-tag color="blue">{{ WORKFLOW_MODULE_TEXT[record.module_id] || record.module_id }}</a-tag>
            </template>
            <template v-else-if="column.key === 'default_backend'">
              <a-tag :color="record.default_backend === 'workflow' ? 'purple' : 'default'">
                {{ AI_BACKEND_TEXT[record.default_backend] || record.default_backend }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'connector_id'">
              <span v-if="record.connector_id">
                {{ getConnectorName(record.connector_id) }}
              </span>
              <span v-else style="color: #999">未绑定</span>
            </template>
            <template v-else-if="column.key === 'page_selectable'">
              <a-tag :color="record.page_selectable ? 'green' : 'default'">
                {{ record.page_selectable ? '允许' : '禁止' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" size="small" @click="openModuleModal(record)">编辑</a-button>
            </template>
          </template>
        </a-table>

        <!-- 模块配置抽屉 -->
        <a-drawer
          v-model:open="moduleModalVisible"
          :title="moduleEditing ? '编辑模块后端配置' : '配置模块后端'"
          width="480"
          @ok="saveModuleConfig"
          :confirm-loading="moduleSaving"
        >
          <a-form layout="vertical">
            <a-form-item label="模块" required>
              <a-select
                v-model:value="moduleForm.module_id"
                :options="WORKFLOW_MODULE_OPTIONS"
                :disabled="!!moduleEditing"
                placeholder="选择模块"
              />
            </a-form-item>
            <a-form-item label="默认执行后端">
              <a-radio-group v-model:value="moduleForm.default_backend">
                <a-radio value="local">本地执行（调用本地 LLM）</a-radio>
                <a-radio value="workflow">外部工作流</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-form-item label="绑定平台连接">
              <a-select
                v-model:value="moduleForm.connector_id"
                :options="connectorOptions"
                allow-clear
                placeholder="选择已配置的平台连接"
              />
            </a-form-item>
            <a-form-item label="外部 Agent 标识">
              <a-input
                v-model:value="moduleForm.external_agent_id"
                placeholder="外部平台的 agent/workflow ID"
              />
              <span class="hint">调用外部平台时作为 agent_id 传给平台</span>
            </a-form-item>
            <a-form-item label="允许页面切换">
              <a-switch v-model:checked="moduleForm.page_selectable" />
              <span class="hint">开启后业务页面提交时可选择 local/workflow</span>
            </a-form-item>
          </a-form>
        </a-drawer>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, EyeOutlined, EyeInvisibleOutlined, CopyOutlined } from '@ant-design/icons-vue'
import {
  listConnectors, createConnector, updateConnector, deleteConnector as deleteConnectorApi,
  getWebhookConfig, updateWebhookConfig,
  listModuleConfigs, upsertModuleConfig, updateModuleConfig as updateModuleConfigApi,
  type WorkflowConnector, type WorkflowWebhookConfig,
  type AgentBackendConfig,
} from '@/api/workflow'
import {
  WORKFLOW_PLATFORM_TEXT, WORKFLOW_PLATFORM_COLOR, WORKFLOW_PLATFORM_OPTIONS,
  WORKFLOW_MODULE_TEXT, WORKFLOW_MODULE_OPTIONS,
  AI_BACKEND_TEXT,
} from '@/constants/enums'

const activeTab = ref('connectors')

// ════════ Tab 1：平台连接 ════════
const connectors = ref<WorkflowConnector[]>([])
const connectorsLoading = ref(false)
const connectorModalVisible = ref(false)
const connectorSaving = ref(false)
const connectorEditing = ref<WorkflowConnector | null>(null)

const connectorForm = reactive({
  name: '',
  platform_type: 'openai_compat',
  base_url: '',
  run_path: '/v1/workflows/run',
  auth_type: 'bearer',
  auth_header: 'Authorization',
  auth_token: '',
  accept_timeout: 30,
  status: 'active',
})

const connectorColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '连接名称', dataIndex: 'name', key: 'name' },
  { title: '平台类型', dataIndex: 'platform_type', key: 'platform_type', width: 120 },
  { title: '服务地址', dataIndex: 'base_url', key: 'base_url', ellipsis: true },
  { title: '凭证', dataIndex: 'auth_token_masked', key: 'auth_token_masked', width: 160 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 140 },
]

async function fetchConnectors() {
  connectorsLoading.value = true
  try {
    const res = await listConnectors()
    connectors.value = res.items
  } finally {
    connectorsLoading.value = false
  }
}

function openConnectorModal(row?: WorkflowConnector) {
  connectorEditing.value = row || null
  if (row) {
    Object.assign(connectorForm, {
      name: row.name,
      platform_type: row.platform_type,
      base_url: row.base_url,
      run_path: row.run_path,
      auth_type: row.auth_type,
      auth_header: row.auth_header,
      auth_token: '', // 编辑时留空表示不修改
      accept_timeout: row.accept_timeout,
      status: row.status,
    })
  } else {
    Object.assign(connectorForm, {
      name: '',
      platform_type: 'openai_compat',
      base_url: '',
      run_path: '/v1/workflows/run',
      auth_type: 'bearer',
      auth_header: 'Authorization',
      auth_token: '',
      accept_timeout: 30,
      status: 'active',
    })
  }
  connectorModalVisible.value = true
}

async function saveConnector() {
  if (!connectorForm.name.trim()) {
    message.warning('请输入连接名称')
    return
  }
  if (!connectorForm.base_url.trim()) {
    message.warning('请输入服务地址')
    return
  }
  connectorSaving.value = true
  try {
    const data: any = { ...connectorForm }
    if (!data.auth_token) delete data.auth_token
    if (connectorEditing.value) {
      await updateConnector(connectorEditing.value.id, data)
      message.success('更新成功')
    } else {
      await createConnector(data)
      message.success('创建成功')
    }
    connectorModalVisible.value = false
    fetchConnectors()
  } finally {
    connectorSaving.value = false
  }
}

function deleteConnector(row: WorkflowConnector) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除连接「${row.name}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteConnectorApi(row.id)
      message.success('删除成功')
      fetchConnectors()
    },
  })
}

const connectorOptions = computed(() =>
  connectors.value.map(c => ({ label: c.name, value: c.id }))
)

function getConnectorName(id: number) {
  return connectors.value.find(c => c.id === id)?.name || `#${id}`
}

// ════════ Tab 2：Webhook 配置 ════════
const webhookConfig = ref<WorkflowWebhookConfig | null>(null)
const webhookLoading = ref(false)
const webhookSaving = ref(false)
const secretVisible = ref(false)

const webhookForm = reactive({
  webhook_url: '',
  enabled: false,
  callback_timeout: 600,
})

function toggleSecretVisible() {
  secretVisible.value = !secretVisible.value
}

async function copySecret() {
  const secret = webhookConfig.value?.secret_plain
  if (!secret) {
    message.warning('尚未生成签名密钥')
    return
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(secret)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = secret
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    message.success('签名密钥已复制到剪贴板')
  } catch {
    message.error('复制失败，请手动复制')
  }
}

async function fetchWebhookConfig() {
  webhookLoading.value = true
  try {
    const cfg = await getWebhookConfig()
    webhookConfig.value = cfg
    webhookForm.webhook_url = cfg.webhook_url
    webhookForm.enabled = cfg.enabled
    webhookForm.callback_timeout = cfg.callback_timeout
  } finally {
    webhookLoading.value = false
  }
}

async function saveWebhook() {
  webhookSaving.value = true
  try {
    const cfg = await updateWebhookConfig({
      webhook_url: webhookForm.webhook_url,
      enabled: webhookForm.enabled,
      callback_timeout: webhookForm.callback_timeout,
    })
    webhookConfig.value = cfg
    message.success('Webhook 配置已保存')
  } finally {
    webhookSaving.value = false
  }
}

async function regenerateSecret() {
  Modal.confirm({
    title: '重新生成签名密钥',
    content: '重新生成后，外部平台需更新回调签名。确定继续？',
    okText: '重新生成',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const cfg = await updateWebhookConfig({ regenerate_secret: true })
      webhookConfig.value = cfg
      message.success('签名密钥已重新生成')
    },
  })
}

// ════════ Tab 3：模块后端配置 ════════
const moduleConfigs = ref<AgentBackendConfig[]>([])
const modulesLoading = ref(false)
const moduleModalVisible = ref(false)
const moduleSaving = ref(false)
const moduleEditing = ref<AgentBackendConfig | null>(null)

const moduleForm = reactive({
  module_id: 'requirement.generate',
  default_backend: 'local',
  connector_id: undefined as number | undefined,
  external_agent_id: '',
  page_selectable: true,
})

const moduleColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '模块', dataIndex: 'module_id', key: 'module_id', width: 160 },
  { title: '默认后端', dataIndex: 'default_backend', key: 'default_backend', width: 120 },
  { title: '绑定连接', dataIndex: 'connector_id', key: 'connector_id' },
  { title: '外部 Agent 标识', dataIndex: 'external_agent_id', key: 'external_agent_id', ellipsis: true },
  { title: '页面切换', dataIndex: 'page_selectable', key: 'page_selectable', width: 100 },
  { title: '操作', key: 'action', width: 80 },
]

async function fetchModuleConfigs() {
  modulesLoading.value = true
  try {
    const res = await listModuleConfigs()
    moduleConfigs.value = res.items
  } finally {
    modulesLoading.value = false
  }
}

function openModuleModal(row?: AgentBackendConfig) {
  moduleEditing.value = row || null
  if (row) {
    Object.assign(moduleForm, {
      module_id: row.module_id,
      default_backend: row.default_backend,
      connector_id: row.connector_id || undefined,
      external_agent_id: row.external_agent_id || '',
      page_selectable: row.page_selectable,
    })
  } else {
    Object.assign(moduleForm, {
      module_id: 'requirement.generate',
      default_backend: 'local',
      connector_id: undefined,
      external_agent_id: '',
      page_selectable: true,
    })
  }
  moduleModalVisible.value = true
}

async function saveModuleConfig() {
  moduleSaving.value = true
  try {
    const data = {
      module_id: moduleForm.module_id,
      default_backend: moduleForm.default_backend,
      connector_id: moduleForm.connector_id || null,
      external_agent_id: moduleForm.external_agent_id || undefined,
      page_selectable: moduleForm.page_selectable,
    }
    if (moduleEditing.value) {
      // 编辑走 PUT
      await updateModuleConfigApi(moduleEditing.value.id, data)
      message.success('更新成功')
    } else {
      await upsertModuleConfig(data)
      message.success('保存成功')
    }
    moduleModalVisible.value = false
    fetchModuleConfigs()
  } finally {
    moduleSaving.value = false
  }
}

onMounted(() => {
  fetchConnectors()
  fetchWebhookConfig()
  fetchModuleConfigs()
})
</script>

<style scoped>
.workflow-config-page { padding: 20px; }
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.tab-toolbar { margin-bottom: 16px; }
.mono { font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 12px; }
.hint { color: #8c8c8c; font-size: 12px; margin-left: 8px; }
</style>
