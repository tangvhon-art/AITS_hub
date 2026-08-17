<template>
  <div class="versions-page">
    <div class="page-header">
      <h2>版本管理</h2>
      <a-button type="primary" @click="openCreate(defaultForm)">
        <template #icon><PlusOutlined /></template>
        新建版本
      </a-button>
    </div>

    <a-card>
      <div style="margin-bottom: 12px">
        <a-space wrap>
          <a-input v-model:value="filterName" placeholder="版本名称" allow-clear style="width: 180px" />
          <a-select v-model:value="filterStatus" placeholder="状态筛选" allow-clear style="width: 140px">
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="active">进行中</a-select-option>
            <a-select-option value="released">已发布</a-select-option>
            <a-select-option value="archived">已归档</a-select-option>
          </a-select>
          <a-range-picker v-model:value="filterDateRange" :placeholder="['开始日期', '结束日期']" />
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="list"
        :loading="loading"
        :pagination="paginationConfig"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'date_range'">
            <span>{{ record.start_date ? formatDate(record.start_date) : '-' }} ~ {{ record.end_date ? formatDate(record.end_date) : '-' }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEdit(record.id, record)">编辑</a-button>
              <a-button type="link" size="small" danger @click="handleDelete(record.id, record.name)">删除</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingId ? '编辑版本' : '新建版本'"
      @ok="submit"
      :confirm-loading="modalLoading"
      width="600px"
    >
      <a-form :model="formData" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="版本名称" required>
              <a-input v-model:value="formData.name" placeholder="例如：v1.0.0" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="状态">
              <a-select v-model:value="formData.status">
                <a-select-option value="draft">草稿</a-select-option>
                <a-select-option value="active">进行中</a-select-option>
                <a-select-option value="released">已发布</a-select-option>
                <a-select-option value="archived">已归档</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="版本描述">
          <a-textarea v-model:value="formData.description" :rows="3" placeholder="请输入版本描述" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="开始时间">
              <a-date-picker v-model:value="formData.start_date" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="结束时间">
              <a-date-picker v-model:value="formData.end_date" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="发布时间">
              <a-date-picker v-model:value="formData.released_at" show-time style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { formatDateTime, formatDate } from '@/utils/date'
import dayjs from 'dayjs'
import {
  getVersions, createVersion, updateVersion, deleteVersion,
  type ProjectVersion
} from '@/api/projectVersions'

const route = useRoute()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

const filterStatus = ref<string | undefined>(undefined)
const filterName = ref<string | undefined>(undefined)
const filterDateRange = ref<[dayjs.Dayjs, dayjs.Dayjs] | undefined>(undefined)

// 使用 useList 封装分页列表逻辑
const { loading, list, total, pagination, loadData: loadVersions, handleTableChange } = useList<ProjectVersion>(
  async (params) => {
    syncToUrl({ status: filterStatus.value, name: filterName.value })
    return getVersions(projectId, {
      status: filterStatus.value,
      name: filterName.value || undefined,
      start_date: filterDateRange.value?.[0]?.format('YYYY-MM-DD'),
      end_date: filterDateRange.value?.[1]?.format('YYYY-MM-DD'),
      ...params,
    })
  },
  { immediate: false },
)

function handleSearch() {
  pagination.current = 1
  loadVersions()
}

const paginationConfig = computed(() => ({
  current: pagination.current,
  pageSize: pagination.pageSize,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '版本名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '日期范围', key: 'date_range', width: 220 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 140 },
]

function statusColor(s?: string) {
  const map: Record<string, string> = { draft: 'default', active: 'green', released: 'blue', archived: 'default' }
  return map[s || ''] || 'default'
}

function statusText(s?: string) {
  const map: Record<string, string> = { draft: '草稿', active: '进行中', released: '已发布', archived: '已归档' }
  return map[s || ''] || s
}

function handleReset() {
  filterStatus.value = undefined
  filterName.value = undefined
  filterDateRange.value = undefined
  pagination.current = 1
  loadVersions()
}

// 新建时的默认表单值
const defaultForm: Partial<ProjectVersion> = {
  name: '', description: '', status: 'draft', start_date: null, end_date: null, released_at: null,
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
} = useCRUD<ProjectVersion>({
  api: {
    create: (data) => createVersion(projectId, data as ProjectVersion),
    update: (id, data) => updateVersion(projectId, id, data),
    remove: (id) => deleteVersion(projectId, id),
  },
  resourceName: '版本',
  onSuccess: loadVersions,
  beforeSubmit: () => {
    if (!formData.name) {
      message.warning('请输入版本名称')
      return false
    }
    return true
  },
})

onMounted(() => {
  if (projectId) {
    const params = loadFromUrl({ status: undefined, name: undefined })
    filterStatus.value = params.status
    filterName.value = params.name
    loadVersions()
  }
})
</script>

<style scoped>
.versions-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
</style>
