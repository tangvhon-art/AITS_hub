<template>
  <div class="defects-page">
    <div class="page-header">
      <h2>缺陷管理</h2>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新建缺陷
      </a-button>
    </div>

    <a-card class="filter-card">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-select v-model:value="filterStatus" placeholder="状态" allow-clear @change="loadDefects">
            <a-select-option value="open">新建</a-select-option>
            <a-select-option value="confirmed">已确认</a-select-option>
            <a-select-option value="resolved">已解决</a-select-option>
            <a-select-option value="closed">已关闭</a-select-option>
            <a-select-option value="reopened">重新打开</a-select-option>
          </a-select>
        </a-col>
        <a-col :span="6">
          <a-select v-model:value="filterSeverity" placeholder="严重程度" allow-clear @change="loadDefects">
            <a-select-option value="blocker">致命</a-select-option>
            <a-select-option value="critical">严重</a-select-option>
            <a-select-option value="major">主要</a-select-option>
            <a-select-option value="minor">次要</a-select-option>
            <a-select-option value="trivial">轻微</a-select-option>
          </a-select>
        </a-col>
      </a-row>
    </a-card>

    <a-card>
      <a-table
        :columns="columns"
        :data-source="defects"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'severity'">
            <a-tag :color="severityColor(record.severity)">{{ severityText(record.severity) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'priority'">
            <a-tag color="blue">{{ record.priority }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="viewDefect(record)">详情</a-button>
              <a-button type="link" size="small" @click="editDefect(record)">编辑</a-button>
              <a-popconfirm title="确定删除此缺陷？" @confirm="deleteDefect(record.id)">
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
      :title="editingDefect ? '编辑缺陷' : '新建缺陷'"
      @ok="handleSubmit"
      :confirm-loading="submitting"
      width="700px"
    >
      <a-form :model="formData" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item label="缺陷标题" required>
              <a-input v-model:value="formData.title" placeholder="请输入缺陷标题" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="严重程度">
              <a-select v-model:value="formData.severity">
                <a-select-option value="blocker">致命</a-select-option>
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">主要</a-select-option>
                <a-select-option value="minor">次要</a-select-option>
                <a-select-option value="trivial">轻微</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="优先级">
              <a-select v-model:value="formData.priority">
                <a-select-option value="P0">P0</a-select-option>
                <a-select-option value="P1">P1</a-select-option>
                <a-select-option value="P2">P2</a-select-option>
                <a-select-option value="P3">P3</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="状态">
              <a-select v-model:value="formData.status">
                <a-select-option value="open">新建</a-select-option>
                <a-select-option value="confirmed">已确认</a-select-option>
                <a-select-option value="resolved">已解决</a-select-option>
                <a-select-option value="closed">已关闭</a-select-option>
                <a-select-option value="reopened">重新打开</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="根因分类">
              <a-select v-model:value="formData.root_cause_category" allow-clear>
                <a-select-option value="frontend">前端</a-select-option>
                <a-select-option value="backend">后端</a-select-option>
                <a-select-option value="data">数据</a-select-option>
                <a-select-option value="environment">环境</a-select-option>
                <a-select-option value="requirement">需求</a-select-option>
                <a-select-option value="other">其他</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="缺陷描述">
          <a-textarea v-model:value="formData.description" :rows="3" placeholder="请输入缺陷描述" />
        </a-form-item>
        <a-form-item label="复现步骤">
          <a-textarea v-model:value="formData.reproduce_steps" :rows="3" placeholder="请输入复现步骤" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="预期结果">
              <a-textarea v-model:value="formData.expected_result" :rows="2" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="实际结果">
              <a-textarea v-model:value="formData.actual_result" :rows="2" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="根因分析">
          <a-textarea v-model:value="formData.root_cause" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="缺陷详情" :footer="null" width="700px">
      <a-descriptions :column="2" bordered v-if="currentDefect">
        <a-descriptions-item label="标题" :span="2">{{ currentDefect.title }}</a-descriptions-item>
        <a-descriptions-item label="严重程度">
          <a-tag :color="severityColor(currentDefect.severity)">{{ severityText(currentDefect.severity) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="优先级">{{ currentDefect.priority }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="statusColor(currentDefect.status)">{{ statusText(currentDefect.status) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="根因分类">{{ currentDefect.root_cause_category || '-' }}</a-descriptions-item>
        <a-descriptions-item label="描述" :span="2">{{ currentDefect.description || '-' }}</a-descriptions-item>
        <a-descriptions-item label="复现步骤" :span="2">{{ currentDefect.reproduce_steps || '-' }}</a-descriptions-item>
        <a-descriptions-item label="预期结果" :span="2">{{ currentDefect.expected_result || '-' }}</a-descriptions-item>
        <a-descriptions-item label="实际结果" :span="2">{{ currentDefect.actual_result || '-' }}</a-descriptions-item>
        <a-descriptions-item label="根因分析" :span="2">{{ currentDefect.root_cause || '-' }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ currentDefect.created_at }}</a-descriptions-item>
        <a-descriptions-item label="更新时间">{{ currentDefect.updated_at }}</a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getDefects, createDefect, updateDefect, deleteDefect as deleteDefectApi, type Defect } from '@/api/defects'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const defects = ref<Defect[]>([])
const filterStatus = ref<string>()
const filterSeverity = ref<string>()
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const modalVisible = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const editingDefect = ref<Defect | null>(null)
const currentDefect = ref<Defect | null>(null)

const formData = ref<Partial<Defect>>({
  title: '',
  description: '',
  severity: 'major',
  priority: 'P2',
  status: 'open',
  root_cause_category: '',
  reproduce_steps: '',
  expected_result: '',
  actual_result: '',
  root_cause: '',
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '根因分类', dataIndex: 'root_cause_category', key: 'root_cause_category', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' as const },
]

async function loadDefects() {
  loading.value = true
  if (!projectId) {
    loading.value = false
    message.error('缺少项目 ID，无法加载缺陷')
    return
  }
  try {
    const res = await getDefects(projectId, {
      status: filterStatus.value,
      severity: filterSeverity.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    defects.value = res.items
    pagination.value.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadDefects()
}

function showCreateModal() {
  editingDefect.value = null
  formData.value = {
    title: '',
    description: '',
    severity: 'major',
    priority: 'P2',
    status: 'open',
    root_cause_category: '',
    reproduce_steps: '',
    expected_result: '',
    actual_result: '',
    root_cause: '',
  }
  modalVisible.value = true
}

function editDefect(record: Defect) {
  editingDefect.value = record
  formData.value = { ...record }
  modalVisible.value = true
}

function viewDefect(record: Defect) {
  currentDefect.value = record
  detailVisible.value = true
}

async function handleSubmit() {
  if (!formData.value.title) {
    message.warning('请输入缺陷标题')
    return
  }
  submitting.value = true
  try {
    if (editingDefect.value) {
      await updateDefect(projectId, editingDefect.value.id!, formData.value)
      message.success('更新成功')
    } else {
      await createDefect(projectId, formData.value)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadDefects()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function deleteDefect(id: number) {
  try {
    await deleteDefectApi(projectId, id)
    message.success('删除成功')
    loadDefects()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function severityColor(s?: string) {
  const map: Record<string, string> = { blocker: 'red', critical: 'orange', major: 'gold', minor: 'blue', trivial: 'default' }
  return map[s || ''] || 'default'
}
function severityText(s?: string) {
  const map: Record<string, string> = { blocker: '致命', critical: '严重', major: '主要', minor: '次要', trivial: '轻微' }
  return map[s || ''] || s
}
function statusColor(s?: string) {
  const map: Record<string, string> = { open: 'red', confirmed: 'orange', resolved: 'green', closed: 'default', reopened: 'orange' }
  return map[s || ''] || 'default'
}
function statusText(s?: string) {
  const map: Record<string, string> = { open: '新建', confirmed: '已确认', resolved: '已解决', closed: '已关闭', reopened: '重新打开' }
  return map[s || ''] || s
}

onMounted(() => {
  if (projectId) loadDefects()
})
</script>

<style scoped>
.defects-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.filter-card { margin-bottom: 16px; }
</style>
