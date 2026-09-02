<template>
  <div>
    <a-card size="small">
      <div class="toolbar">
        <a-select v-model:value="filterType" style="width: 160px" allow-clear placeholder="全部类型" @change="load">
          <a-select-option value="llm">大模型</a-select-option>
          <a-select-option value="agent">内置Agent</a-select-option>
          <a-select-option value="external_agent">外部工作流</a-select-option>
          <a-select-option value="business">业务入口</a-select-option>
        </a-select>
        <div style="flex: 1"></div>
        <a-button type="primary" @click="openModal()"><PlusOutlined /> 新增被测对象</a-button>
      </div>
      <a-table :data-source="list" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="名称" data-index="name" />
        <a-table-column title="类型" data-index="target_type" width="110">
          <template #default="{ text }"><a-tag :color="typeColor(text)">{{ typeText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="版本标识" data-index="version_tag" width="110" />
        <a-table-column title="绑定信息" width="220">
          <template #default="{ record }">
            <span v-if="record.target_type === 'llm'">LLM配置 #{{ record.llm_config_id }}</span>
            <span v-else-if="record.target_type === 'agent'">Agent: {{ record.agent_type }}</span>
            <span v-else-if="record.target_type === 'external_agent'">{{ record.service_url }}{{ record.call_path }}（{{ authTypeText(record.auth_type) }}）</span>
            <span v-else>场景: {{ record.business_scene }}</span>
          </template>
        </a-table-column>
        <a-table-column title="描述" data-index="description" ellipsis />
        <a-table-column title="操作" width="140">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openModal(record)">编辑</a-button>
              <a-popconfirm title="确认停用该被测对象？" @confirm="remove(record)">
                <a-button type="link" danger size="small">停用</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-modal v-model:open="modalOpen" :title="form.id ? '编辑被测对象' : '新增被测对象'" @ok="save" :confirm-loading="saving" width="560">
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item label="类型" required>
          <a-select v-model:value="form.target_type">
            <a-select-option value="llm">大模型（绑定 LLM 配置）</a-select-option>
            <a-select-option value="agent">内置 Agent</a-select-option>
            <a-select-option value="external_agent">外部工作流（填写服务地址与鉴权）</a-select-option>
            <a-select-option value="business">业务入口</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'llm'" label="LLM 配置">
          <a-select v-model:value="form.llm_config_id" allow-clear>
            <a-select-option v-for="c in llmConfigs" :key="c.id" :value="c.id">{{ c.name }}（{{ c.model_name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'agent'" label="内置 Agent 类型">
          <a-input v-model:value="form.agent_type" placeholder="如 case_generator / execution_agent" />
        </a-form-item>
        <a-form-item v-if="form.target_type === 'external_agent'" label="服务地址 / 调用路径 / 鉴权方式" required>
          <a-input v-model:value="form.service_url" placeholder="服务地址，如 https://gateway.example.com" style="width: 100%" />
          <a-input v-model:value="form.call_path" placeholder="调用路径，如 /api/workflow/run" style="width: 100%; margin-top: 8px" />
          <div style="display: flex; gap: 8px; margin-top: 8px">
            <a-select v-model:value="form.auth_type" style="width: 140px" placeholder="鉴权方式">
              <a-select-option value="none">无鉴权</a-select-option>
              <a-select-option value="bearer">Bearer Token</a-select-option>
              <a-select-option value="apikey">API Key</a-select-option>
              <a-select-option value="custom">自定义 Header</a-select-option>
            </a-select>
            <a-input v-model:value="form.auth_token" placeholder="鉴权凭证（Token / API Key）" style="flex: 1" />
            <a-input v-if="form.auth_type === 'custom'" v-model:value="form.auth_header" placeholder="Header 名，如 X-Api-Key" style="width: 160px" />
          </div>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'business'" label="业务场景标识">
          <a-input v-model:value="form.business_scene" placeholder="如 order_query / knowledge_qa" />
        </a-form-item>
        <a-form-item label="版本标识"><a-input v-model:value="form.version_tag" placeholder="如 v0.1 / 2026Q3" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="form.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { evalTargetApi, EVAL_TYPE_TEXT } from '@/api/eval'
import { getLLMConfigs } from '@/api/llm'

const list = ref<any[]>([])
const loading = ref(false)
const filterType = ref<string>()
const modalOpen = ref(false)
const saving = ref(false)
const llmConfigs = ref<any[]>([])
const form = ref<any>({})

const typeText = (t: string) => (EVAL_TYPE_TEXT as any)[t] || t
const typeColor = (t: string) => ({ llm: 'blue', agent: 'cyan', external_agent: 'purple', business: 'green' } as any)[t] || 'default'
const authTypeText = (t?: string) => ({ none: '无鉴权', bearer: 'Bearer', apikey: 'API Key', custom: '自定义Header' } as any)[t || 'none'] || '无鉴权'


const load = async () => {
  loading.value = true
  try {
    list.value = await evalTargetApi.list(filterType.value)
  } finally {
    loading.value = false
  }
}

const openModal = (record?: any) => {
  form.value = record
    ? { ...record }
    : { name: '', target_type: 'llm', status: 'active', auth_type: 'none', auth_header: 'Authorization' }
  modalOpen.value = true
}

const save = async () => {
  if (!form.value.name) { message.warning('请填写名称'); return }
  if (form.value.target_type === 'external_agent' && (!form.value.service_url || !form.value.call_path)) {
    message.warning('外部工作流需填写服务地址与调用路径')
    return
  }
  saving.value = true
  try {
    if (form.value.id) await evalTargetApi.update(form.value.id, form.value)
    else await evalTargetApi.create(form.value)
    message.success('保存成功')
    modalOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

const remove = async (record: any) => {
  await evalTargetApi.remove(record.id)
  message.success('已停用')
  load()
}

onMounted(async () => {
  try { llmConfigs.value = await getLLMConfigs() } catch (e) { /* 忽略 */ }
})
onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
