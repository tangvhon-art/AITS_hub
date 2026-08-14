<template>
  <div class="api-executions">
    <div class="page-header">
      <h2>执行记录</h2>
    </div>

    <a-card>
      <div class="filter-bar">
        <a-select v-model:value="typeFilter" placeholder="执行类型" style="width: 120px" allow-clear @change="loadData">
          <a-select-option value="case">用例</a-select-option>
          <a-select-option value="scenario">场景</a-select-option>
          <a-select-option value="debug">调试</a-select-option>
        </a-select>
        <a-select v-model:value="statusFilter" placeholder="状态" style="width: 120px" allow-clear @change="loadData">
          <a-select-option value="passed">通过</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
          <a-select-option value="partial">部分通过</a-select-option>
          <a-select-option value="running">执行中</a-select-option>
        </a-select>
      </div>

      <a-table
        :columns="columns"
        :data-source="dataSource"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">{{ getStatusName(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'pass_rate'">
            <a-progress :percent="Math.round(record.pass_rate * 100)" size="small" />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="handleView(record)">查看详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiExecutionsApi, type ApiExecution } from '@/api/apiTest'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const loading = ref(false)
const typeFilter = ref('')
const statusFilter = ref('')
const dataSource = ref<ApiExecution[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '类型', dataIndex: 'execution_type', key: 'execution_type', width: 80 },
  { title: '名称', dataIndex: 'ref_name', key: 'ref_name' },
  { title: '状态', key: 'status', width: 100 },
  { title: '总步骤', dataIndex: 'total_steps', key: 'total_steps', width: 80 },
  { title: '通过', dataIndex: 'passed_steps', key: 'passed_steps', width: 80 },
  { title: '失败', dataIndex: 'failed_steps', key: 'failed_steps', width: 80 },
  { title: '通过率', key: 'pass_rate', width: 150 },
  { title: '耗时(ms)', dataIndex: 'total_duration', key: 'total_duration', width: 100 },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at', width: 180 },
  { title: '操作', key: 'action', width: 100 },
]

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    passed: 'green', failed: 'red', partial: 'orange',
    running: 'blue', pending: 'default'
  }
  return colors[status] || 'default'
}

const getStatusName = (status: string) => {
  const names: Record<string, string> = {
    passed: '通过', failed: '失败', partial: '部分通过',
    running: '执行中', pending: '等待中'
  }
  return names[status] || status
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await apiExecutionsApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      execution_type: typeFilter.value,
      status: statusFilter.value,
    })
    dataSource.value = res.items
    pagination.value.total = res.total
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag: any) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadData()
}

const handleView = (record: ApiExecution) => {
  router.push(`/projects/${projectId}/api-executions/${record.id}`)
}

onMounted(() => loadData())
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
