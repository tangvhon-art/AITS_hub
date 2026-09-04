<template>
  <div class="prompts-page">
    <PageHeader title="Prompt 管理">
      <template #extra>
        <a-button @click="handleSeedDefaults" :loading="seeding">初始化默认模板</a-button>
        <a-button type="primary" @click="openCreate(defaultForm)">
          <template #icon><PlusOutlined /></template>
          新建 Prompt
        </a-button>
      </template>
    </PageHeader>

    <!-- 搜索筛选栏（五件套） -->
    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="分类">
          <a-select v-model:value="filterCategory" allow-clear placeholder="全部分类" style="width: 150px">
            <a-select-option value="case_generation">用例生成</a-select-option>
            <a-select-option value="case_review">用例评审</a-select-option>
            <a-select-option value="api_doc_generation">接口文档生成</a-select-option>
            <a-select-option value="api_case_generation">接口用例生成</a-select-option>
            <a-select-option value="requirement_generation">需求生成</a-select-option>
            <a-select-option value="report_generation">报告生成</a-select-option>
            <a-select-option value="script_generation">脚本生成</a-select-option>
            <a-select-option value="other">其他</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-input v-model:value="searchKeyword" placeholder="搜索名称/描述" allow-clear style="width: 200px" @keyup.enter="handleSearch" />
        </a-form-item>
      </a-form>
    </SearchBar>

    <!-- 服务端分页表格（五件套） -->
    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      @change="handleTableChange"
    >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
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
              <MdView :content="record.system_prompt" />
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
          <a-button v-if="!record.is_default || isAdmin" type="link" size="small" @click="openEdit(record.id, record)">编辑</a-button>
          <a-button v-if="!record.is_default || isAdmin" type="link" size="small" danger @click="handleDelete(record.id, record.name)">删除</a-button>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 编辑/新建弹窗（五件套 FormModal） -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑 Prompt' : '新建 Prompt'"
      :loading="modalLoading"
      :model="formData"
      width="700px"
      ok-text="确定"
      cancel-text="取消"
      @ok="submit"
    >
      <a-form-item label="名称" required>
        <a-input v-model:value="formData.name" placeholder="Prompt 名称" />
      </a-form-item>
      <a-form-item label="分类">
        <a-select v-model:value="formData.category" style="width: 100%">
          <a-select-option value="case_generation">用例生成</a-select-option>
          <a-select-option value="case_review">用例评审</a-select-option>
          <a-select-option value="api_doc_generation">接口文档生成</a-select-option>
          <a-select-option value="api_case_generation">接口用例生成</a-select-option>
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
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <a-switch v-model:checked="previewMode" size="small" />
          <span style="color: #999; font-size: 12px;">{{ previewMode ? '预览模式（只读）' : '编辑模式' }}</span>
        </div>
        <a-textarea
          v-if="!previewMode"
          v-model:value="formData.system_prompt"
          :rows="8"
          placeholder="作为 system 角色的提示词，定义 AI 的行为和输出要求"
        />
        <MdView v-else :content="formData.system_prompt" />
      </a-form-item>
      <a-form-item label="设为默认">
        <a-switch v-model:checked="formData.is_default" />
        <span style="margin-left: 8px; color: #999">设为该分类下的默认 Prompt</span>
      </a-form-item>
    </FormModal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import MdView from '@/components/MdView.vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'
import { promptsApi, type Prompt, type PromptCreate } from '@/api/prompts'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.is_admin === true)
const seeding = ref(false)
const previewMode = ref(false)

// 新建时的默认表单值
const defaultForm: PromptCreate = {
  name: '',
  description: '',
  category: 'case_generation',
  system_prompt: '',
  is_default: false,
  status: 'active',
}

// ── 服务端分页列表（五件套：useList + DataTable）──
const filterCategory = ref<string>()
const searchKeyword = ref('')
const {
  loading,
  list,
  total,
  pagination,
  loadData,
  handleTableChange,
} = useList<Prompt>(
  (params) =>
    promptsApi.list({
      category: filterCategory.value,
      keyword: searchKeyword.value,
      page: params.page,
      page_size: params.page_size,
    }) as Promise<{ items: Prompt[]; total: number }>,
)

/** 搜索：回到第一页再加载 */
function handleSearch() {
  pagination.current = 1
  loadData()
}

/** 重置筛选并回到第一页 */
function handleReset() {
  filterCategory.value = undefined
  searchKeyword.value = ''
  pagination.current = 1
  loadData()
}

// ── 新增/编辑/删除（五件套：useCRUD + FormModal）──
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
  api_doc_generation: '接口文档生成',
  api_case_generation: '接口用例生成',
  requirement_generation: '需求生成',
  report_generation: '报告生成',
  script_generation: '脚本生成',
  other: '其他',
})[c] || c

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
</script>

<style scoped>
.prompts-page { padding: 0; }
.prompt-preview {
  color: #666;
  font-size: 13px;
}
</style>

<style>
.md-tooltip {
  max-height: 500px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
}
.md-tooltip h1, .md-tooltip h2, .md-tooltip h3 {
  margin: 8px 0 4px;
  font-size: 14px;
  font-weight: 600;
}
.md-tooltip p { margin: 4px 0; }
.md-tooltip table {
  border-collapse: collapse;
  width: 100%;
  margin: 4px 0;
}
.md-tooltip th, .md-tooltip td {
  border: 1px solid #555;
  padding: 2px 6px;
  font-size: 12px;
}
.md-tooltip th { background: #333; }
.md-tooltip code {
  background: #333;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}
.md-tooltip pre {
  background: #222;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
}
.md-tooltip ul, .md-tooltip ol {
  margin: 4px 0;
  padding-left: 20px;
}

.md-preview {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
  background: #fafafa;
  font-size: 13px;
  line-height: 1.7;
}
.md-preview h1, .md-preview h2, .md-preview h3 {
  margin: 10px 0 6px;
  font-weight: 600;
}
.md-preview h1 { font-size: 18px; }
.md-preview h2 { font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.md-preview h3 { font-size: 14px; }
.md-preview p { margin: 6px 0; }
.md-preview table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.md-preview th, .md-preview td {
  border: 1px solid #d9d9d9;
  padding: 4px 8px;
  font-size: 13px;
}
.md-preview th { background: #f5f5f5; font-weight: 600; }
.md-preview code {
  background: #f0f0f0;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
  color: #c41d7f;
}
.md-preview pre {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}
.md-preview ul, .md-preview ol {
  margin: 6px 0;
  padding-left: 20px;
}
.md-preview li { margin: 2px 0; }
</style>
