<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>操作审计日志</h2>
    </div>

    <a-card>
      <a-form layout="inline" style="margin-bottom: 16px">
        <a-form-item label="操作类型">
          <a-select v-model:value="filterAction" allow-clear placeholder="全部" style="width: 150px" @change="loadLogs">
            <a-select-option value="create">创建</a-select-option>
            <a-select-option value="update">更新</a-select-option>
            <a-select-option value="delete">删除</a-select-option>
            <a-select-option value="login">登录</a-select-option>
            <a-select-option value="export">导出</a-select-option>
            <a-select-option value="import">导入</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="资源类型">
          <a-select v-model:value="filterResourceType" allow-clear placeholder="全部" style="width: 150px" @change="loadLogs">
            <a-select-option value="project">项目</a-select-option>
            <a-select-option value="requirement">需求</a-select-option>
            <a-select-option value="case">用例</a-select-option>
            <a-select-option value="run">执行</a-select-option>
            <a-select-option value="defect">缺陷</a-select-option>
            <a-select-option value="report">报告</a-select-option>
            <a-select-option value="plan">计划</a-select-option>
            <a-select-option value="environment">环境</a-select-option>
            <a-select-option value="user">用户</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" allow-clear placeholder="全部" style="width: 120px" @change="loadLogs">
            <a-select-option value="success">成功</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>

      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-tag :color="getActionColor(record.action)">{{ getActionText(record.action) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'resource_type'">
            <a-tag>{{ getResourceText(record.resource_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'success' ? 'green' : 'red'">
              {{ record.status === 'success' ? '成功' : '失败' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'detail'">
            <a-button type="link" size="small" @click="showDetail(record)">查看</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal v-model:open="showDetailModal" title="操作详情" width="600px" :footer="null">
      <div v-if="currentLog">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="操作用户">{{ currentLog.username || currentLog.user_id || '未知' }}</a-descriptions-item>
          <a-descriptions-item label="操作类型">{{ getActionText(currentLog.action) }}</a-descriptions-item>
          <a-descriptions-item label="资源类型">{{ getResourceText(currentLog.resource_type) }}</a-descriptions-item>
          <a-descriptions-item label="资源ID">{{ currentLog.resource_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="资源名称" :span="2">{{ currentLog.resource_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="IP地址">{{ currentLog.ip_address || '-' }}</a-descriptions-item>
          <a-descriptions-item label="操作状态">
            <a-tag :color="currentLog.status === 'success' ? 'green' : 'red'">
              {{ currentLog.status === 'success' ? '成功' : '失败' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="操作时间" :span="2">{{ $formatDateTime(currentLog.created_at) }}</a-descriptions-item>
        </a-descriptions>
        <a-divider>操作详情</a-divider>
        <pre v-if="currentLog.detail && Object.keys(currentLog.detail).length > 0" class="detail-json">
{{ JSON.stringify(currentLog.detail, null, 2) }}
        </pre>
        <a-empty v-else description="无详细信息" />
        <a-divider v-if="currentLog.error_message">错误信息</a-divider>
        <a-alert v-if="currentLog.error_message" :message="currentLog.error_message" type="error" show-icon />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getAuditLogs, type AuditLog } from '@/api/auditLogs'

const loading = ref(false)
const logs = ref<AuditLog[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const filterAction = ref<string>()
const filterResourceType = ref<string>()
const filterStatus = ref<string>()

const showDetailModal = ref(false)
const currentLog = ref<AuditLog | null>(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '操作用户', dataIndex: 'username', key: 'username', width: 120 },
  { title: '操作类型', dataIndex: 'action', key: 'action', width: 100 },
  { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 100 },
  { title: '资源名称', dataIndex: 'resource_name', key: 'resource_name', ellipsis: true },
  { title: 'IP地址', dataIndex: 'ip_address', key: 'ip_address', width: 130 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '操作时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '详情', key: 'detail', width: 80 }
]

function getActionColor(action?: string) {
  const map: Record<string, string> = {
    create: 'green',
    update: 'blue',
    delete: 'red',
    login: 'purple',
    export: 'orange',
    import: 'cyan'
  }
  return map[action || ''] || 'default'
}

function getActionText(action?: string) {
  const map: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    login: '登录',
    logout: '登出',
    export: '导出',
    import: '导入'
  }
  return map[action || ''] || action
}

function getResourceText(type?: string) {
  const map: Record<string, string> = {
    project: '项目',
    requirement: '需求',
    case: '用例',
    run: '执行',
    defect: '缺陷',
    report: '报告',
    plan: '计划',
    environment: '环境',
    user: '用户',
    knowledge: '知识库'
  }
  return map[type || ''] || type
}

function showDetail(record: AuditLog) {
  currentLog.value = record
  showDetailModal.value = true
}

async function loadLogs() {
  loading.value = true
  try {
    const res = await getAuditLogs({
      action: filterAction.value,
      resource_type: filterResourceType.value,
      status: filterStatus.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize
    })
    logs.value = res.items
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
  loadLogs()
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.audit-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.detail-json {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
}
</style>
