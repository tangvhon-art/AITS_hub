<template>
  <div class="api-definition-edit">
    <div class="page-header">
      <a-button @click="$router.back()">
        <template #icon><ArrowLeftOutlined /></template>
        返回
      </a-button>
      <h2>{{ isEdit ? '编辑接口' : '新建接口' }}</h2>
    </div>

    <a-form :model="form" layout="vertical" ref="formRef">
      <a-card title="基本信息">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-form-item label="请求方法">
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
            <a-form-item label="接口路径">
              <a-input v-model:value="form.path" placeholder="/api/users" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="接口名称">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所属分组">
              <a-tree-select
                v-model:value="form.module_id"
                :tree-data="moduleTree"
                placeholder="选择分组"
                allow-clear
                tree-default-expand-all
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="接口描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
      </a-card>

      <a-card title="请求参数" style="margin-top: 16px">
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="headers" tab="Headers">
            <a-table :data-source="form.headers" :columns="paramColumns" row-key="key" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="removeParam('headers', index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="addParam('headers')">+ 添加 Header</a-button>
          </a-tab-pane>
          <a-tab-pane key="query" tab="Query Params">
            <a-table :data-source="form.query_params" :columns="paramColumns" row-key="key" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="removeParam('query_params', index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="addParam('query_params')">+ 添加参数</a-button>
          </a-tab-pane>
          <a-tab-pane key="body" tab="Body">
            <a-radio-group v-model:value="form.body_type" style="margin-bottom: 12px">
              <a-radio value="none">none</a-radio>
              <a-radio value="json">JSON</a-radio>
              <a-radio value="form-data">form-data</a-radio>
              <a-radio value="x-www-form-urlencoded">x-www-form-urlencoded</a-radio>
              <a-radio value="raw">raw</a-radio>
            </a-radio-group>
            <a-textarea
              v-if="form.body_type === 'json' || form.body_type === 'raw'"
              v-model:value="bodyContent"
              :rows="8"
              placeholder='{"key": "value"}'
              style="font-family: monospace"
            />
            <a-table
              v-else-if="form.body_type === 'form-data' || form.body_type === 'x-www-form-urlencoded'"
              :data-source="bodyParams"
              :columns="paramColumns"
              row-key="key"
              size="small"
              pagination="false"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="bodyParams.splice(index, 1)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button v-if="form.body_type !== 'none'" type="dashed" block style="margin-top: 8px" @click="bodyParams.push({ key: '', value: '', enabled: true })">+ 添加字段</a-button>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <div class="form-actions">
        <a-button @click="$router.back()">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </div>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { apiDefinitionsApi, apiModulesApi } from '@/api/apiTest'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const apiId = route.params.apiId
const isEdit = computed(() => apiId && apiId !== 'new')

const formRef = ref()
const saving = ref(false)
const activeTab = ref('headers')
const moduleTree = ref<any[]>([])

const form = ref<any>({
  name: '',
  method: 'GET',
  path: '',
  description: '',
  module_id: null,
  headers: [],
  query_params: [],
  path_params: [],
  body_type: 'none',
  body_content: null,
  response_examples: [],
})

const bodyContent = computed({
  get: () => typeof form.value.body_content === 'string' ? form.value.body_content : JSON.stringify(form.value.body_content, null, 2),
  set: (val: string) => {
    try { form.value.body_content = JSON.parse(val) } catch { form.value.body_content = val }
  }
})

const bodyParams = computed({
  get: () => Array.isArray(form.value.body_content) ? form.value.body_content : [],
  set: (val) => { form.value.body_content = val }
})

const paramColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '参数名', dataIndex: 'key', key: 'key' },
  { title: '参数值', dataIndex: 'value', key: 'value' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '操作', key: 'action', width: 60 },
]

const addParam = (type: string) => {
  form.value[type].push({ key: '', value: '', description: '', enabled: true })
}

const removeParam = (type: string, index: number) => {
  form.value[type].splice(index, 1)
}

const loadModules = async () => {
  try {
    const modules = await apiModulesApi.getTree(projectId)
    moduleTree.value = modules.map((m: any) => ({ title: m.name, value: m.id, children: m.children }))
  } catch {}
}

const loadData = async () => {
  if (!isEdit.value) return
  const data = await apiDefinitionsApi.get(projectId, Number(apiId))
  Object.assign(form.value, data)
}

const handleSave = async () => {
  saving.value = true
  try {
    if (isEdit.value) {
      await apiDefinitionsApi.update(projectId, Number(apiId), form.value)
      message.success('更新成功')
    } else {
      await apiDefinitionsApi.create(projectId, form.value)
      message.success('创建成功')
    }
    router.back()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadModules()
  loadData()
  // 新建时从 query 参数读取默认分组
  if (!isEdit.value && route.query.module_id) {
    form.value.module_id = Number(route.query.module_id)
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
}
.form-actions {
  margin-top: 24px;
  text-align: right;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
