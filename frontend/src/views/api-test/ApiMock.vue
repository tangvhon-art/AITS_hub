<template>
  <div class="api-mock">
    <div class="page-header">
      <h2>Mock 服务</h2>
      <a-button type="primary" @click="handleCreate">
        <template #icon><PlusOutlined /></template>
        新建 Mock
      </a-button>
    </div>

    <a-alert
      message="Mock 服务地址"
      :description="mockServiceUrl"
      type="info"
      show-icon
      style="margin-bottom: 16px"
    />

    <a-card>
      <a-table
        :columns="columns"
        :data-source="dataSource"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="getMethodColor(record.method)">{{ record.method }}</a-tag>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-switch :checked="record.enabled" @change="(checked: boolean) => handleToggle(record, checked)" />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
              <a-popconfirm title="确定删除该Mock？" @confirm="handleDelete(record)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 编辑弹窗 -->
    <a-modal v-model:open="showModal" :title="editingId ? '编辑Mock' : '新建Mock'" width="700px">
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-form-item label="方法">
              <a-select v-model:value="form.method">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="PATCH">PATCH</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="18">
            <a-form-item label="路径">
              <a-input v-model:value="form.path" placeholder="/api/users" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="响应状态码">
              <a-input-number v-model:value="form.response_status" :min="100" :max="599" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="延迟(ms)">
              <a-input-number v-model:value="form.delay_ms" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="启用">
              <a-switch v-model:checked="form.enabled" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="响应头">
          <a-textarea v-model:value="responseHeadersText" :rows="3" placeholder='{"Content-Type": "application/json"}' style="font-family: monospace" />
        </a-form-item>
        <a-form-item label="响应体">
          <a-textarea v-model:value="form.response_body" :rows="8" placeholder='{"code": 0, "message": "success"}' style="font-family: monospace" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-button @click="showModal = false">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { apiMockApi, type ApiMockExpectation } from '@/api/apiTest'

const route = useRoute()
const projectId = Number(route.params.id)

const mockServiceUrl = computed(() => `${window.location.origin}/mock/${projectId}/{path}`)

const loading = ref(false)
const saving = ref(false)
const dataSource = ref<ApiMockExpectation[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const showModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref<any>({
  name: '',
  method: 'GET',
  path: '',
  response_status: 200,
  response_headers: {},
  response_body: '',
  delay_ms: 0,
  enabled: true,
})

const responseHeadersText = computed({
  get: () => JSON.stringify(form.value.response_headers, null, 2),
  set: (val: string) => {
    try { form.value.response_headers = JSON.parse(val) } catch { form.value.response_headers = {} }
  }
})

const columns = [
  { title: '方法', key: 'method', width: 80 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '路径', dataIndex: 'path', key: 'path' },
  { title: '状态码', dataIndex: 'response_status', key: 'response_status', width: 80 },
  { title: '命中次数', dataIndex: 'hit_count', key: 'hit_count', width: 100 },
  { title: '启用', key: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 140 },
]

const getMethodColor = (method: string) => {
  const colors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }
  return colors[method] || 'default'
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await apiMockApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
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

const handleCreate = () => {
  editingId.value = null
  form.value = {
    name: '',
    method: 'GET',
    path: '',
    response_status: 200,
    response_headers: {},
    response_body: '',
    delay_ms: 0,
    enabled: true,
  }
  showModal.value = true
}

const handleEdit = (record: ApiMockExpectation) => {
  editingId.value = record.id
  Object.assign(form.value, record)
  showModal.value = true
}

const handleSave = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await apiMockApi.update(projectId, editingId.value, form.value)
      message.success('更新成功')
    } else {
      await apiMockApi.create(projectId, form.value)
      message.success('创建成功')
    }
    showModal.value = false
    loadData()
  } finally {
    saving.value = false
  }
}

const handleDelete = async (record: ApiMockExpectation) => {
  await apiMockApi.delete(projectId, record.id)
  message.success('删除成功')
  loadData()
}

const handleToggle = async (record: ApiMockExpectation, checked: boolean) => {
  await apiMockApi.update(projectId, record.id, { enabled: checked })
  record.enabled = checked
}

onMounted(() => loadData())
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
</style>
