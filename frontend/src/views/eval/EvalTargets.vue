<template>
  <div>
    <a-card size="small">
      <SearchBar @search="load" @reset="resetFilters">
        <a-form layout="inline">
<a-form-item label="类型">
<a-select v-model:value="filterType" style="width: 130px" allow-clear placeholder="全部类型">
          <a-select-option value="llm">大模型</a-select-option>
          <a-select-option value="agent">内置Agent</a-select-option>
          <a-select-option value="external_agent">外部工作流</a-select-option>
          <a-select-option value="business">业务入口</a-select-option>
        </a-select>
</a-form-item>
        <a-form-item label="状态">
<a-select v-model:value="filterStatus" style="width: 130px" allow-clear placeholder="全部状态">
          <a-select-option value="active">正常</a-select-option>
          <a-select-option value="inactive">已停用</a-select-option>
          <a-select-option value="deleted">已删除</a-select-option>
        </a-select>
</a-form-item>
        <a-form-item label="名称">
<a-input v-model:value="keyword" placeholder="搜索名称" style="width: 200px" allow-clear />
</a-form-item>
        </a-form>
        <template #extra>
          <a-button type="primary" @click="openModal()"><PlusOutlined /> 新增被测对象</a-button>
        </template>
      </SearchBar><DataTable :data-source="filteredList" row-key="id" :loading="loading" size="small">
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
        <a-table-column title="状态" width="100">
          <template #default="{ record }">
            <a-tag v-if="record.is_deleted" color="default">已停用</a-tag>
            <a-tag v-else-if="record.status === 'inactive'" color="orange">已停用</a-tag>
            <a-tag v-else color="green">正常</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="操作" width="170">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openModal(record)">编辑</a-button>
              <a-button v-if="!record.is_deleted && record.status === 'active'" type="link" danger size="small" @click="confirmDelete(record, () => toggleStatus(record, 'inactive'))">停用</a-button>
              <a-button
                v-else-if="!record.is_deleted && record.status === 'inactive'"
                type="link" size="small" @click="toggleStatus(record, 'active')"
              >启用</a-button>
              <a-button v-if="record.is_deleted" type="link" size="small" @click="confirmDelete(record, () => restore(record))">恢复</a-button>
            </a-space>
          </template>
        </a-table-column>
      </DataTable>
    </a-card>

    <FormModal
      v-model:visible="modalOpen"
      title="form.id ? '编辑被测对象' : '新增被测对象'"
      :loading="saving"
      width="560"
      @ok="save"
    >
      <a-form-item label="名称" required><a-form-item label="筛选">
<a-input v-model:value="form.name" />
</a-form-item></a-form-item>
        <a-form-item label="类型" required>
          <a-form-item label="筛选">
<a-select v-model:value="form.target_type">
            <a-select-option value="llm">大模型（绑定 LLM 配置）</a-select-option>
            <a-select-option value="agent">内置 Agent</a-select-option>
            <a-select-option value="external_agent">外部工作流（填写服务地址与鉴权）</a-select-option>
            <a-select-option value="business">业务入口</a-select-option>
          </a-select>
</a-form-item>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'llm'" label="LLM 配置">
          <a-form-item label="筛选">
<a-select v-model:value="form.llm_config_id" allow-clear>
            <a-select-option v-for="c in llmConfigs" :key="c.id" :value="c.id">{{ c.name }}（{{ c.model_name }}）</a-select-option>
          </a-select>
</a-form-item>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'agent'" label="内置 Agent 类型">
          <a-form-item label="筛选">
<a-input v-model:value="form.agent_type" placeholder="如 case_generator / execution_agent" />
</a-form-item>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'external_agent'" label="服务地址 / 调用路径 / 鉴权方式" required>
          <a-form-item label="筛选">
<a-input v-model:value="form.service_url" placeholder="服务地址，如 https://gateway.example.com" style="width: 100%" />
</a-form-item>
          <a-form-item label="筛选">
<a-input v-model:value="form.call_path" placeholder="调用路径，如 /api/workflow/run" style="width: 100%; margin-top: 8px" />
</a-form-item>
          <div style="display: flex; gap: 8px; margin-top: 8px">
            <a-form-item label="筛选">
<a-select v-model:value="form.auth_type" style="width: 140px" placeholder="鉴权方式">
              <a-select-option value="none">无鉴权</a-select-option>
              <a-select-option value="bearer">Bearer Token</a-select-option>
              <a-select-option value="apikey">API Key</a-select-option>
              <a-select-option value="custom">自定义 Header</a-select-option>
            </a-select>
</a-form-item>
            <a-form-item label="筛选">
<a-input v-model:value="form.auth_token" placeholder="鉴权凭证（Token / API Key）" style="flex: 1" />
</a-form-item>
            <a-form-item label="筛选">
<a-input v-if="form.auth_type === 'custom'" v-model:value="form.auth_header" placeholder="Header 名，如 X-Api-Key" style="width: 160px" />
</a-form-item>
          </div>
        </a-form-item>
        <a-form-item v-if="form.target_type === 'business'" label="业务场景标识">
          <a-form-item label="筛选">
<a-input v-model:value="form.business_scene" placeholder="如 order_query / knowledge_qa" />
</a-form-item>
        </a-form-item>
        <a-form-item label="版本标识"><a-form-item label="筛选">
<a-input v-model:value="form.version_tag" placeholder="如 v0.1 / 2026Q3" />
</a-form-item></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="form.description" :rows="2" /></a-form-item>
    </FormModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { evalTargetApi, EVAL_TYPE_TEXT } from '@/api/eval'
import { getLLMConfigs } from '@/api/llm'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useConfirmDelete } from '@/composables/useConfirmDelete'
import SearchBar from '@/components/SearchBar.vue'
const { confirmDelete } = useConfirmDelete('测评目标')

const list = ref<any[]>([])
const loading = ref(false)
const filterType = ref<string>()
const filterStatus = ref<string>()
const keyword = ref('')
const modalOpen = ref(false)
const saving = ref(false)
const llmConfigs = ref<any[]>([])
const form = ref<any>({})

const typeText = (t: string) => (EVAL_TYPE_TEXT as any)[t] || t
const typeColor = (t: string) => ({ llm: 'blue', agent: 'cyan', external_agent: 'purple', business: 'green' } as any)[t] || 'default'
const authTypeText = (t?: string) => ({ none: '无鉴权', bearer: 'Bearer', apikey: 'API Key', custom: '自定义Header' } as any)[t || 'none'] || '无鉴权'

// 查询条件：类型 / 状态 / 名称（前端本地过滤，列表已全量返回）
const filteredList = computed(() => {
  let l = list.value
  if (filterType.value) l = l.filter(x => x.target_type === filterType.value)
  if (filterStatus.value) {
    if (filterStatus.value === 'active') l = l.filter(x => !x.is_deleted && x.status === 'active')
    else if (filterStatus.value === 'inactive') l = l.filter(x => !x.is_deleted && x.status === 'inactive')
    else if (filterStatus.value === 'deleted') l = l.filter(x => x.is_deleted)
  }
  const kw = keyword.value.trim().toLowerCase()
  if (kw) l = l.filter(x => (x.name || '').toLowerCase().includes(kw))
  return l
})


const resetFilters = () => {
  filterType.value = ''; filterStatus.value = ''; keyword.value = ''
  load()
}

const load = async () => {
  loading.value = true
  try {
    list.value = await evalTargetApi.list()
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

// 停用/启用切换（status 字段，记录仍展示在列表）
const toggleStatus = async (record: any, status: string) => {
  await evalTargetApi.update(record.id, { status })
  message.success(status === 'inactive' ? '已停用' : '已启用')
  load()
}

// 恢复已软删记录
const restore = async (record: any) => {
  await evalTargetApi.restore(record.id)
  message.success('已恢复')
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
