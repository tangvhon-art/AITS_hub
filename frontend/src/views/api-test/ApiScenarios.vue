<template>
  <div class="api-scenarios">
    <div class="page-header">
      <h2>场景编排</h2>
      <a-button type="primary" @click="handleCreate">
        <template #icon><PlusOutlined /></template>
        新建场景
      </a-button>
    </div>

    <a-card>
      <div class="filter-bar">
        <a-input-search v-model:value="keyword" placeholder="搜索场景名称" style="width: 250px" @search="loadData" />
        <a-space>
          <a-button type="primary" @click="loadData">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
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
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleRun(record)">执行</a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
              <a-popconfirm title="确定删除该场景？" @confirm="handleDelete(record)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { apiScenariosApi, type ApiScenario } from '@/api/apiTest'
const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const loading = ref(false)
const keyword = ref('')
const dataSource = ref<ApiScenario[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const columns = [
  { title: '场景名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 180 },
]

const loadData = async () => {
  loading.value = true
  try {
    const res = await apiScenariosApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: keyword.value,
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

function handleReset() {
  keyword.value = ''
  pagination.value.current = 1
  loadData()
}

const handleCreate = () => {
  router.push(`/projects/${projectId}/api-test/scenarios/new`)
}

const handleEdit = (record: ApiScenario) => {
  router.push(`/projects/${projectId}/api-test/scenarios/${record.id}`)
}

const handleRun = async (record: ApiScenario) => {
  try {
    const res = await apiScenariosApi.run(projectId, record.id, {})
    message.success('执行已提交')
    if (res.execution_id) {
      router.push(`/projects/${projectId}/api-test/executions/${res.execution_id}`)
    }
  } catch {}
}

const handleDelete = async (record: ApiScenario) => {
  await apiScenariosApi.delete(projectId, record.id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  const params = { keyword: '' }
  keyword.value = params.keyword
  loadData()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
