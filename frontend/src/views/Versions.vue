<template>
  <div class="versions-page">
    <div class="page-header">
      <h2>版本管理</h2>
      <a-button type="primary" @click="openCreateModal">
        <template #icon><PlusOutlined /></template>
        新建版本
      </a-button>
    </div>

    <a-card>
      <div style="margin-bottom: 12px">
        <a-space>
          <a-select v-model:value="filterStatus" placeholder="状态筛选" allow-clear style="width: 140px">
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="active">进行中</a-select-option>
            <a-select-option value="released">已发布</a-select-option>
            <a-select-option value="archived">已归档</a-select-option>
          </a-select>
          <a-button type="primary" @click="loadVersions">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="versions"
        :loading="loading"
        :pagination="pagination"
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
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm title="确定删除此版本？" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingVersion ? '编辑版本' : '新建版本'"
      @ok="handleSubmit"
      :confirm-loading="submitting"
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { formatDateTime, formatDate } from '@/utils/date'
import {
  getVersions, createVersion, updateVersion, deleteVersion,
  type ProjectVersion
} from '@/api/projectVersions'

const route = useRoute()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const submitting = ref(false)
const versions = ref<ProjectVersion[]>([])
const filterStatus = ref<string | undefined>(undefined)
const pagination = ref({ current: 1, pageSize: 50, total: 0 })

const modalVisible = ref(false)
const editingVersion = ref<ProjectVersion | null>(null)
const formData = ref<Partial<ProjectVersion>>({})

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

async function loadVersions() {
  syncToUrl({ status: filterStatus.value })
  loading.value = true
  try {
    const res = await getVersions(projectId, {
      status: filterStatus.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    versions.value = res.items
    pagination.value.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载版本列表失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  filterStatus.value = undefined
  loadVersions()
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadVersions()
}

function openCreateModal() {
  editingVersion.value = null
  formData.value = { name: '', description: '', status: 'draft', start_date: null, end_date: null, released_at: null }
  modalVisible.value = true
}

function openEditModal(record: ProjectVersion) {
  editingVersion.value = record
  formData.value = { ...record }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formData.value.name) {
    message.warning('请输入版本名称')
    return
  }
  submitting.value = true
  try {
    if (editingVersion.value?.id) {
      await updateVersion(projectId, editingVersion.value.id, formData.value)
      message.success('更新成功')
    } else {
      await createVersion(projectId, formData.value as ProjectVersion)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadVersions()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deleteVersion(projectId, id)
    message.success('删除成功')
    loadVersions()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  if (projectId) {
    const params = loadFromUrl({ status: undefined })
    filterStatus.value = params.status
    loadVersions()
  }
})
</script>

<style scoped>
.versions-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
</style>
