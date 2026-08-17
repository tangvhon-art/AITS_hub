<template>
  <div class="data-pools">
    <div class="page-header">
      <h2>测试数据池</h2>
      <a-button type="primary" @click="handleCreate"><PlusOutlined /> 新建数据池</a-button>
    </div>
    <a-card>
      <div class="filter-bar">
        <a-input-search v-model:value="keyword" placeholder="搜索名称" allow-clear style="width: 250px" @search="loadData" />
        <a-select v-model:value="typeFilter" allow-clear placeholder="数据类型" style="width: 150px">
          <a-select-option value="static">静态数据</a-select-option>
          <a-select-option value="dynamic">动态生成</a-select-option>
          <a-select-option value="generated">自动生成</a-select-option>
        </a-select>
        <a-space>
          <a-button type="primary" @click="loadData">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>
      <a-table :columns="columns" :data-source="dataSource" :loading="loading" :pagination="pagination" row-key="id" @change="handleTableChange">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'data_type'">
            <a-tag :color="typeColor(record.data_type)">{{ typeText(record.data_type) }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button size="small" type="link" @click="handlePreview(record)">预览</a-button>
              <a-button size="small" type="link" @click="handleEdit(record)">编辑</a-button>
              <a-popconfirm title="确定删除？" @confirm="handleDelete(record)">
                <a-button size="small" type="link" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal v-model:open="previewVisible" title="数据预览" width="800px" :footer="null">
      <a-table :columns="previewColumns" :data-source="previewData" :pagination="false" size="small" :scroll="{ y: 400 }" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { dataPoolsApi, type TestDataPool } from '@/api/dataPools'
import { useUrlSearch } from '@/composables/useUrlSearch'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const keyword = ref('')
const typeFilter = ref<string | undefined>(undefined)
const dataSource = ref<TestDataPool[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const previewVisible = ref(false)
const previewData = ref<any[]>([])
const previewColumns = ref<any[]>([])

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '数据类型', key: 'data_type', width: 120 },
  { title: '字段数', key: 'field_count', width: 80, customRender: ({ record }: any) => record.schema?.length || 0 },
  { title: '数据行数', key: 'data_count', width: 90, customRender: ({ record }: any) => record.data?.length || 0 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' as const },
]

const typeColor = (t: string) => ({ static: 'blue', dynamic: 'green', generated: 'orange' })[t] || 'default'
const typeText = (t: string) => ({ static: '静态数据', dynamic: '动态生成', generated: '自动生成' })[t] || t

async function loadData() {
  syncToUrl({ keyword: keyword.value, type: typeFilter.value })
  loading.value = true
  try {
    const res = await dataPoolsApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: keyword.value || undefined,
      data_type: typeFilter.value,
    })
    dataSource.value = res.items
    pagination.value.total = res.total
  } catch { } finally {
    loading.value = false
  }
}

function handleTableChange(p: any) {
  pagination.value.current = p.current
  pagination.value.pageSize = p.pageSize
  loadData()
}

function handleReset() {
  keyword.value = ''
  typeFilter.value = undefined
  pagination.value.current = 1
  loadData()
}

function handleCreate() {
  router.push(`/projects/${projectId}/data-pools/new`)
}

function handleEdit(record: TestDataPool) {
  router.push(`/projects/${projectId}/data-pools/${record.id}`)
}

async function handlePreview(record: TestDataPool) {
  try {
    const res = await dataPoolsApi.preview(projectId, record.id, 10)
    previewData.value = res.data
    if (res.data.length > 0) {
      previewColumns.value = Object.keys(res.data[0]).map(key => ({ title: key, dataIndex: key, key, ellipsis: true }))
    }
    previewVisible.value = true
  } catch { }
}

async function handleDelete(record: TestDataPool) {
  try {
    await dataPoolsApi.delete(projectId, record.id)
    message.success('删除成功')
    loadData()
  } catch { }
}

onMounted(() => {
  const params = loadFromUrl({ keyword: '', type: undefined })
  keyword.value = params.keyword
  typeFilter.value = params.type
  loadData()
})
</script>

<style scoped>
.data-pools { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>
