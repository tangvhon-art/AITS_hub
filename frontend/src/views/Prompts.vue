<template>
  <div class="prompts-page">
    <div class="page-header">
      <h2>Prompt 管理</h2>
      <div class="header-actions">
        <a-button @click="handleSeedDefaults" :loading="seeding">初始化默认模板</a-button>
        <a-button type="primary" @click="openCreate(defaultForm)">
          <template #icon><PlusOutlined /></template>
          新建 Prompt
        </a-button>
      </div>
    </div>

    <a-form layout="inline" style="margin-bottom: 16px">
      <a-form-item label="分类">
        <a-select v-model:value="filterCategory" allow-clear placeholder="全部分类" style="width: 150px">
          <a-select-option value="case_generation">用例生成</a-select-option>
          <a-select-option value="case_review">用例评审</a-select-option>
          <a-select-option value="api_test">API 测试</a-select-option>
          <a-select-option value="requirement_generation">需求生成</a-select-option>
          <a-select-option value="report_generation">报告生成</a-select-option>
          <a-select-option value="script_generation">脚本生成</a-select-option>
          <a-select-option value="other">其他</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="关键词">
        <a-input v-model:value="searchKeyword" placeholder="搜索名称/描述" allow-clear style="width: 200px" @keyup.enter="handleSearch" />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-table
      :columns="columns"
      :data-source="filteredPrompts"
      :loading="loading"
      row-key="id"
      :pagination="{ pageSize: 20, showSizeChanger: true }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <span>{{ record.name }}</span>
          <a-tag v-if="record.is_default" color="blue" style="margin-left: 8px">默认</a-tag>
        </template>
        <template v-else-if="column.key === 'category'">
          <a-tag>{{ categoryText(record.category) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'system_prompt'">
          <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '800px' }">
            <template #title>
              <div style="white-space: pre-wrap; max-height: 500px; overflow-y: auto">{{ record.system_prompt }}</div>
            </template>
            <span class="prompt-preview">{{ record.system_prompt.slice(0, 80) }}{{ record.system_prompt.length > 80 ? '...' : '' }}</span>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">
            {{ record.status === 'active' ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openEdit(record.id, record)">编辑</a-button>
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.name)">删除</a-button>
        </template>
      </template>
    </a-table>

    <!-- 编辑/新建弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingId ? '编辑 Prompt' : '新建 Prompt'"
      width="700px"
      @ok="submit"
      :confirm-loading="modalLoading"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="formData.name" placeholder="Prompt 名称" />
        </a-form-item>
        <a-form-item label="分类">
          <a-select v-model:value="formData.category" style="width: 100%">
            <a-select-option value="case_generation">用例生成</a-select-option>
            <a-select-option value="case_review">用例评审</a-select-option>
            <a-select-option value="api_test">API 测试</a-select-option>
            <a-select-option value="requirement_generation">需求生成</a-select-option>
            <a-select-option value="report_generation">报告生成</a-select-option>
            <a-select-option value="script_generation">脚本生成</a-select-option>
            <a-select-option value="other">其他</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="formData.description" placeholder="Prompt 描述说明" />
        </a-form-item>
        <a-form-item label="System 提示词" required>
          <a-textarea
            v-model:value="formData.system_prompt"
            :rows="8"
            placeholder="作为 system 角色的提示词，定义 AI 的行为和输出要求"
          />
        </a-form-item>
        <a-form-item label="设为默认">
          <a-switch v-model:checked="formData.is_default" />
          <span style="margin-left: 8px; color: #999">设为该分类下的默认 Prompt</span>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { useCRUD } from '@/composables/useCRUD'
import { promptsApi, type Prompt, type PromptCreate } from '@/api/prompts'

const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const dataSource = ref<Prompt[]>([])
const filterCategory = ref<string>()
const searchKeyword = ref('')
const seeding = ref(false)

// 新建时的默认表单值
const defaultForm: PromptCreate = {
  name: '',
  description: '',
  category: 'case_generation',
  system_prompt: '',
  is_default: false,
  status: 'active',
}

// 使用 useCRUD 封装新增/编辑/删除逻辑
const {
  modalVisible,
  modalLoading,
  editingId,
  formData,
  openCreate,
  openEdit,
  submit,
  handleDelete,
} = useCRUD<Prompt>({
  api: {
    create: (data) => promptsApi.create(data as PromptCreate),
    update: (id, data) => promptsApi.update(id, data),
    remove: (id) => promptsApi.delete(id),
  },
  resourceName: 'Prompt',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.name?.trim()) {
      message.warning('请输入名称')
      return false
    }
    if (!formData.system_prompt?.trim()) {
      message.warning('请输入 System 提示词')
      return false
    }
    return true
  },
})

const columns = [
  { title: '名称', key: 'name', width: 200 },
  { title: '分类', key: 'category', width: 120 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: 'System 提示词', key: 'system_prompt', ellipsis: true },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 120 },
]

const categoryText = (c: string) => ({
  case_generation: '用例生成',
  case_review: '用例评审',
  api_test: 'API 测试',
  requirement_generation: '需求生成',
  report_generation: '报告生成',
  script_generation: '脚本生成',
  other: '其他',
})[c] || c

const filteredPrompts = computed(() => {
  let result = dataSource.value
  if (filterCategory.value) {
    result = result.filter(p => p.category === filterCategory.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(p =>
      p.name?.toLowerCase().includes(kw) ||
      p.description?.toLowerCase().includes(kw)
    )
  }
  return result
})

function handleSearch() {
  syncToUrl({ category: filterCategory.value, keyword: searchKeyword.value })
}

function handleReset() {
  filterCategory.value = undefined
  searchKeyword.value = ''
  syncToUrl({ category: filterCategory.value, keyword: searchKeyword.value })
}

async function loadData() {
  loading.value = true
  try {
    dataSource.value = await promptsApi.list()
  } catch {
    message.error('加载 Prompt 列表失败')
  } finally {
    loading.value = false
  }
}

async function handleSeedDefaults() {
  seeding.value = true
  try {
    const res = await promptsApi.seedDefaults()
    message.success(res.detail)
    loadData()
  } catch {
    message.error('初始化失败')
  } finally {
    seeding.value = false
  }
}

onMounted(() => {
  const params = loadFromUrl({ category: undefined, keyword: '' })
  filterCategory.value = params.category
  searchKeyword.value = params.keyword
  loadData()
})
</script>

<style scoped>
.prompts-page { padding: 0; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.prompt-preview {
  color: #666;
  font-size: 13px;
}
</style>
