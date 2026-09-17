<template>
  <div>
    <PageHeader title="测试用例集">
      <template #extra>
        <a-button type="primary" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          新建用例集
        </a-button>
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
        <a-form layout="inline">
          <a-form-item label="用例集名称">
            <a-input v-model:value="filterName" placeholder="用例集名称" allow-clear style="width: 220px" @pressEnter="handleSearch" />
          </a-form-item>
        </a-form>
      </SearchBar>

      <DataTable
        :columns="columns"
        :data-source="list"
        :loading="loading"
        row-key="id"
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openMind(record)">
                <template #icon><ShareAltOutlined /></template>
                打开导图
              </a-button>
              <a-button type="link" size="small" @click="openAddCases(record)">添加用例</a-button>
              <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" size="small" danger @click="handleDelete(record)">删除</a-button>
            </a-space>
          </template>
        </template>
      </DataTable>
    </a-card>

    <!-- 新建/编辑用例集 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑用例集' : '新建用例集'"
      :loading="modalLoading"
      width="560px"
      @ok="submit"
      @cancel="modalVisible = false"
    >
      <a-form-item label="用例集名称" required>
        <a-input v-model:value="formData.name" placeholder="例如：AI测评模块回归用例集" />
      </a-form-item>
      <a-form-item label="用例集描述">
        <a-textarea v-model:value="formData.description" :rows="3" placeholder="描述该用例集的业务场景/测试轮次" />
      </a-form-item>
    </FormModal>

    <!-- 添加用例弹窗：支持按用例 / 按需求 / 按模块 三种方式 -->
    <a-modal
      v-model:open="addVisible"
      title="添加用例到用例集"
      width="720px"
      :confirm-loading="adding"
      @ok="doAddCases"
      @cancel="addVisible = false"
    >
      <div v-if="currentSuite" style="margin-bottom: 12px; padding: 8px 12px; background: #f5f7fa; border-radius: 6px;">
        <span style="color: #606266;">目标用例集：</span>
        <span style="font-weight: 500;">{{ currentSuite.name }}</span>
      </div>

      <a-tabs v-model:activeKey="addMode">
        <!-- 方式一：按用例 -->
        <a-tab-pane key="cases" tab="按用例选择">
          <a-form layout="inline" style="margin-bottom: 12px;">
            <a-form-item label="模块">
              <a-select v-model:value="caseFilter.module" placeholder="全部模块" allow-clear style="width: 160px" @change="loadAvailableCases(1)">
                <a-select-option v-for="m in availableModules" :key="m" :value="m">{{ m }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="关键字">
              <a-input v-model:value="caseFilter.keyword" placeholder="用例标题" allow-clear style="width: 160px" @pressEnter="loadAvailableCases(1)" />
            </a-form-item>
            <a-form-item>
              <a-button @click="loadAvailableCases(1)">查询</a-button>
            </a-form-item>
          </a-form>
          <a-table
            size="small"
            row-key="id"
            :columns="caseColumns"
            :data-source="availableCases"
            :loading="availableLoading"
            :pagination="{ current: availablePage, pageSize: availablePageSize, total: availableTotal, showSizeChanger: false }"
            :row-selection="{ selectedRowKeys: selectedCaseIds, onChange: (keys: any[]) => { selectedCaseIds = keys } }"
            @change="(p: any) => loadAvailableCases(p.current)"
          />
        </a-tab-pane>

        <!-- 方式二：按需求 -->
        <a-tab-pane key="reqs" tab="按需求选择">
          <a-form layout="inline" style="margin-bottom: 12px;">
            <a-form-item label="需求标题">
              <a-input v-model:value="reqFilter.keyword" placeholder="需求标题" allow-clear style="width: 200px" @pressEnter="loadReqs(1)" />
            </a-form-item>
            <a-form-item>
              <a-button @click="loadReqs(1)">查询</a-button>
            </a-form-item>
          </a-form>
          <a-table
            size="small"
            row-key="id"
            :columns="reqColumns"
            :data-source="reqList"
            :loading="reqLoading"
            :pagination="{ current: reqPage, pageSize: 10, total: reqTotal, showSizeChanger: false }"
            :row-selection="{ selectedRowKeys: selectedReqIds, onChange: (keys: any[]) => { selectedReqIds = keys } }"
            @change="(p: any) => loadReqs(p.current)"
          />
          <div style="margin-top: 8px; color: #888;">按需求关联：将该需求下全部有效用例加入用例集（可在导图中按模块分组）</div>
        </a-tab-pane>

        <!-- 方式三：按模块 -->
        <a-tab-pane key="modules" tab="按模块选择">
          <a-table
            size="small"
            row-key="module"
            :columns="moduleColumns"
            :data-source="moduleList"
            :pagination="false"
            :row-selection="{ selectedRowKeys: selectedModuleNames, onChange: (keys: any[]) => { selectedModuleNames = keys } }"
          />
          <div style="margin-top: 8px; color: #888;">按模块关联：将所选模块下的全部有效用例加入用例集</div>
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ShareAltOutlined } from '@ant-design/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import {
  getCaseSuites,
  createCaseSuite,
  updateCaseSuite,
  deleteCaseSuite,
  addCasesToSuite,
  getAvailableCases,
} from '@/api/caseSuites'
import { getRequirements } from '@/api/cases'
import { formatDateTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

// ── 列表 ──
const columns = [
  { title: '用例集名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 90 },
  { title: '模块数', dataIndex: 'module_count', key: 'module_count', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 260 },
]
const list = ref<any[]>([])
const loading = ref(false)
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const filterName = ref('')

async function loadData(page = 1) {
  loading.value = true
  try {
    const data = await getCaseSuites(projectId, {
      name: filterName.value || undefined,
      page,
      page_size: pagination.pageSize,
    })
    list.value = data.items
    pagination.total = data.total
    pagination.current = data.page
  } finally {
    loading.value = false
  }
}
function handleSearch() { loadData(1) }
function handleReset() { filterName.value = ''; loadData(1) }
function handleTableChange(p: any) { loadData(p.current) }

// ── 新建/编辑 ──
const modalVisible = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const formData = reactive({ name: '', description: '' })

function openCreate() {
  editingId.value = null
  formData.name = ''
  formData.description = ''
  modalVisible.value = true
}
function openEdit(record: any) {
  editingId.value = record.id
  formData.name = record.name
  formData.description = record.description || ''
  modalVisible.value = true
}
async function submit() {
  if (!formData.name.trim()) {
    message.warning('请输入用例集名称')
    return
  }
  modalLoading.value = true
  try {
    if (editingId.value) {
      await updateCaseSuite(projectId, editingId.value, { name: formData.name.trim(), description: formData.description })
      message.success('用例集已更新')
    } else {
      await createCaseSuite(projectId, { name: formData.name.trim(), description: formData.description })
      message.success('用例集已创建')
    }
    modalVisible.value = false
    loadData(pagination.current)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

function handleDelete(record: any) {
  Modal.confirm({
    title: '删除用例集',
    content: `确定删除用例集「${record.name}」？仅移除集合关系，不影响用例本身。`,
    okText: '删除',
    okType: 'danger',
    async onOk() {
      try {
        await deleteCaseSuite(projectId, record.id)
        message.success('用例集已删除')
        loadData(pagination.current)
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '删除失败')
      }
    },
  })
}

function openMind(record: any) {
  router.push(`/projects/${projectId}/case-suites/${record.id}/mind`)
}

// ── 添加用例弹窗 ──
const addVisible = ref(false)
const adding = ref(false)
const currentSuite = ref<any>(null)
const addMode = ref('cases')

// 方式一：按用例
const availableCases = ref<any[]>([])
const availableLoading = ref(false)
const availableModules = ref<string[]>([])
const availablePage = ref(1)
const availablePageSize = 8
const availableTotal = ref(0)
const selectedCaseIds = ref<number[]>([])
const caseFilter = reactive({ module: undefined as string | undefined, keyword: '' })
const caseColumns = [
  { title: '用例标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 160 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
]

async function loadAvailableCases(page = 1) {
  availableLoading.value = true
  try {
    const data = await getAvailableCases(projectId, {
      module: caseFilter.module,
      keyword: caseFilter.keyword || undefined,
      page,
      page_size: availablePageSize,
    })
    availableCases.value = data.items
    availableTotal.value = data.total
    availablePage.value = data.page
    if (data.modules) availableModules.value = data.modules
  } finally {
    availableLoading.value = false
  }
}

// 方式二：按需求
const reqList = ref<any[]>([])
const reqLoading = ref(false)
const reqPage = ref(1)
const reqTotal = ref(0)
const selectedReqIds = ref<number[]>([])
const reqFilter = reactive({ keyword: '' })
const reqColumns = [
  { title: '需求标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
]

async function loadReqs(page = 1) {
  reqLoading.value = true
  try {
    const data: any = await getRequirements(projectId, { keyword: reqFilter.keyword || undefined, page, page_size: 10 })
    const items = Array.isArray(data) ? data : data.items || data.list || []
    reqList.value = items
    reqTotal.value = Array.isArray(data) ? items.length : data.total ?? items.length
    reqPage.value = page
  } finally {
    reqLoading.value = false
  }
}

// 方式三：按模块
const moduleList = ref<any[]>([])
const selectedModuleNames = ref<string[]>([])
const moduleColumns = [
  { title: '模块名', dataIndex: 'module', key: 'module' },
]

function openAddCases(record: any) {
  currentSuite.value = record
  addMode.value = 'cases'
  selectedCaseIds.value = []
  selectedReqIds.value = []
  selectedModuleNames.value = []
  addVisible.value = true
  loadAvailableCases(1)
  loadReqs(1)
  loadModules()
}

async function loadModules() {
  try {
    const data = await getAvailableCases(projectId, { page: 1, page_size: 1 })
    moduleList.value = (data.modules || []).map((m: string) => ({ module: m }))
  } catch {
    moduleList.value = []
  }
}

async function doAddCases() {
  if (!currentSuite.value) return
  const payload: any = {}
  if (addMode.value === 'cases') {
    if (!selectedCaseIds.value.length) {
      message.warning('请选择要加入的用例')
      return
    }
    payload.case_ids = selectedCaseIds.value
  } else if (addMode.value === 'reqs') {
    if (!selectedReqIds.value.length) {
      message.warning('请选择要关联的需求')
      return
    }
    payload.req_ids = selectedReqIds.value
  } else {
    if (!selectedModuleNames.value.length) {
      message.warning('请选择要关联的模块')
      return
    }
    payload.module_names = selectedModuleNames.value
  }
  adding.value = true
  try {
    const res = await addCasesToSuite(projectId, currentSuite.value.id, payload)
    message.success(res.message || '已加入')
    addVisible.value = false
    loadData(pagination.current)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

onMounted(() => loadData(1))
</script>

<style scoped>
:deep(.ant-table-cell) { padding: 8px 12px !important; }
</style>
