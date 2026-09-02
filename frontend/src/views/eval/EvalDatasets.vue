<template>
  <div>
    <a-card size="small">
      <div class="toolbar">
        <a-select v-model:value="filterType" style="width: 160px" allow-clear placeholder="全部类型" @change="load">
          <a-select-option value="ai_judge">AI裁判</a-select-option>
          <a-select-option value="agent">Agent交互</a-select-option>
          <a-select-option value="business">业务落地</a-select-option>
          <a-select-option value="redteam">对抗红队</a-select-option>
          <a-select-option value="manual">人工</a-select-option>
        </a-select>
        <div style="flex: 1"></div>
        <a-button type="primary" @click="openDsModal()"><PlusOutlined /> 新增数据集</a-button>
      </div>
      <a-table :data-source="list" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="名称" data-index="name" />
        <a-table-column title="类型" data-index="eval_type" width="110">
          <template #default="{ text }"><a-tag :color="typeColor(text)">{{ typeText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="来源" data-index="source" width="90">
          <template #default="{ text }">{{ sourceText(text) }}</template>
        </a-table-column>
        <a-table-column title="版本" data-index="version" width="90" />
        <a-table-column title="用例数" data-index="case_count" width="90" />
        <a-table-column title="操作" width="230">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openCases(record)">管理用例</a-button>
              <a-button type="link" size="small" @click="openDsModal(record)">编辑</a-button>
              <a-popconfirm title="确认归档该数据集？" @confirm="removeDs(record)">
                <a-button type="link" danger size="small">归档</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <!-- 数据集新增/编辑 -->
    <a-modal v-model:open="dsModal" :title="dsForm.id ? '编辑数据集' : '新增数据集'" @ok="saveDs" :confirm-loading="saving" width="480">
      <a-form :model="dsForm" layout="vertical">
        <a-form-item label="名称" required><a-input v-model:value="dsForm.name" /></a-form-item>
        <a-form-item label="类型" required>
          <a-select v-model:value="dsForm.eval_type">
            <a-select-option value="ai_judge">AI裁判</a-select-option>
            <a-select-option value="agent">Agent交互</a-select-option>
            <a-select-option value="business">业务落地</a-select-option>
            <a-select-option value="redteam">对抗红队</a-select-option>
            <a-select-option value="manual">人工</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="版本"><a-input v-model:value="dsForm.version" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="dsForm.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>

    <!-- 用例管理抽屉 -->
    <a-drawer :open="casesDrawer" :title="`用例管理 - ${currentDs?.name || ''}`" width="900" @close="casesDrawer = false">
      <div class="toolbar">
        <a-input v-model:value="caseKeyword" placeholder="搜索用例标题/内容" style="width: 200px" @pressEnter="loadCases" />
        <a-button @click="loadCases">搜索</a-button>
        <div style="flex: 1"></div>
        <a-upload :before-upload="handleImport" :show-upload-list="false" accept=".json">
          <a-button>JSON 批量导入</a-button>
        </a-upload>
        <a-button type="primary" @click="openCaseModal()"><PlusOutlined /> 新增用例</a-button>
      </div>
      <a-table :data-source="cases" row-key="id" :loading="caseLoading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="标题" data-index="title" ellipsis />
        <a-table-column title="类型" width="120">
          <template #default="{ record }">{{ record.attack_type || record.category || '-' }}</template>
        </a-table-column>
        <a-table-column title="难度" data-index="difficulty" width="70" />
        <a-table-column title="操作" width="130">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openCaseModal(record)">编辑</a-button>
              <a-popconfirm title="确认删除？" @confirm="removeCase(record)">
                <a-button type="link" danger size="small">删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table-column>
      </a-table>

      <a-modal v-model:open="caseModal" :title="caseForm.id ? '编辑用例' : '新增用例'" @ok="saveCase" :confirm-loading="saving" width="640">
        <a-form :model="caseForm" layout="vertical">
          <a-form-item label="标题" required><a-input v-model:value="caseForm.title" /></a-form-item>
          <a-form-item label="Prompt / 输入 / 攻击载荷" required><a-textarea v-model:value="caseForm.prompt" :rows="3" /></a-form-item>
          <a-form-item label="预期输出 / 判定规则"><a-textarea v-model:value="caseForm.expected_output" :rows="2" /></a-form-item>
          <a-row :gutter="12">
            <a-col :span="8"><a-form-item label="难度"><a-select v-model:value="caseForm.difficulty"><a-select-option value="P0">P0</a-select-option><a-select-option value="P1">P1</a-select-option><a-select-option value="P2">P2</a-select-option><a-select-option value="P3">P3</a-select-option></a-select></a-form-item></a-col>
            <a-col :span="8"><a-form-item label="攻击类型（红队）"><a-input v-model:value="caseForm.attack_type" placeholder="jailbreak/injection/..." /></a-form-item></a-col>
            <a-col :span="8"><a-form-item label="场景分类"><a-input v-model:value="caseForm.category" /></a-form-item></a-col>
          </a-row>
          <a-form-item label="约束条件"><a-textarea v-model:value="caseForm.constraints" :rows="2" /></a-form-item>
        </a-form>
      </a-modal>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { evalDatasetApi } from '@/api/eval'

const list = ref<any[]>([])
const loading = ref(false)
const filterType = ref<string>()
const dsModal = ref(false)
const dsForm = ref<any>({})
const saving = ref(false)
const currentDs = ref<any>()
const casesDrawer = ref(false)
const cases = ref<any[]>([])
const caseLoading = ref(false)
const caseKeyword = ref('')
const caseModal = ref(false)
const caseForm = ref<any>({})

const typeText = (t: string) => ({ ai_judge: 'AI裁判', manual: '人工', agent: 'Agent交互', business: '业务落地', redteam: '对抗红队' } as any)[t] || t
const typeColor = (t: string) => ({ ai_judge: 'blue', manual: 'purple', agent: 'cyan', business: 'green', redteam: 'red' } as any)[t] || 'default'
const sourceText = (s: string) => ({ builtin: '内置', custom: '自定义', import: '导入', gray: '灰度' } as any)[s] || s

const load = async () => {
  loading.value = true
  try {
    list.value = await evalDatasetApi.list(filterType.value)
  } finally {
    loading.value = false
  }
}

const openDsModal = (record?: any) => {
  dsForm.value = record ? { ...record } : { name: '', eval_type: 'ai_judge', source: 'custom' }
  dsModal.value = true
}
const saveDs = async () => {
  if (!dsForm.value.name) { message.warning('请填写名称'); return }
  saving.value = true
  try {
    if (dsForm.value.id) await evalDatasetApi.update(dsForm.value.id, dsForm.value)
    else await evalDatasetApi.create(dsForm.value)
    message.success('保存成功'); dsModal.value = false; load()
  } finally { saving.value = false }
}
const removeDs = async (record: any) => {
  await evalDatasetApi.remove(record.id); message.success('已归档'); load()
}

const openCases = (record: any) => {
  currentDs.value = record
  casesDrawer.value = true
  loadCases()
}
const loadCases = async () => {
  if (!currentDs.value) return
  caseLoading.value = true
  try {
    const res: any = await evalDatasetApi.cases(currentDs.value.id, { keyword: caseKeyword.value, page: 1, page_size: 50 })
    cases.value = res.items || []
  } finally { caseLoading.value = false }
}
const openCaseModal = (record?: any) => {
  caseForm.value = record ? { ...record } : { title: '', prompt: '', difficulty: 'P2' }
  caseModal.value = true
}
const saveCase = async () => {
  if (!caseForm.value.title) { message.warning('请填写标题'); return }
  saving.value = true
  try {
    if (caseForm.value.id) await evalDatasetApi.updateCase(caseForm.value.id, caseForm.value)
    else await evalDatasetApi.createCase(currentDs.value.id, caseForm.value)
    message.success('保存成功'); caseModal.value = false; loadCases(); load()
  } finally { saving.value = false }
}
const removeCase = async (record: any) => {
  await evalDatasetApi.removeCase(record.id); message.success('已删除'); loadCases(); load()
}
const handleImport = (file: File) => {
  const reader = new FileReader()
  reader.onload = async () => {
    try {
      const arr = JSON.parse(String(reader.result))
      if (!Array.isArray(arr)) throw new Error('格式错误')
      const res: any = await evalDatasetApi.importCases(currentDs.value.id, arr)
      message.success(res.message || '导入完成'); loadCases(); load()
    } catch (e: any) {
      message.error('导入失败: ' + e.message)
    }
  }
  reader.readAsText(file)
  return false
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
</style>
