<template>
  <div class="api-case-edit">
    <div class="page-header">
      <a-button @click="$router.back()">
        <template #icon><ArrowLeftOutlined /></template>
        返回
      </a-button>
      <h2>{{ isEdit ? '编辑用例' : '新建用例' }}</h2>
    </div>

    <a-form :model="form" layout="vertical">
      <a-card title="基本信息">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="用例名称">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item label="优先级">
              <a-select v-model:value="form.priority">
                <a-select-option value="P0">P0</a-select-option>
                <a-select-option value="P1">P1</a-select-option>
                <a-select-option value="P2">P2</a-select-option>
                <a-select-option value="P3">P3</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="请求方法">
              <a-select v-model:value="form.method">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="关联接口">
              <a-select v-model:value="form.api_id" show-search placeholder="选择接口" allow-clear>
                <a-select-option v-for="api in apiList" :key="api.id" :value="api.id">
                  [{{ api.method }}] {{ api.name }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="请求路径">
          <a-input v-model:value="form.path" placeholder="/api/users/{{id}}" />
        </a-form-item>
        <a-form-item label="用例描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
      </a-card>

      <a-card title="请求配置" style="margin-top: 16px">
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="headers" tab="Headers">
            <a-table :data-source="form.headers" :columns="paramColumns" row-key="key" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="form.headers.splice(index, 1)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="form.headers.push({ key: '', value: '', enabled: true })">+ 添加</a-button>
          </a-tab-pane>
          <a-tab-pane key="params" tab="Query">
            <a-table :data-source="form.query_params" :columns="paramColumns" row-key="key" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="form.query_params.splice(index, 1)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="form.query_params.push({ key: '', value: '', enabled: true })">+ 添加</a-button>
          </a-tab-pane>
          <a-tab-pane key="body" tab="Body">
            <a-radio-group v-model:value="form.body_type" style="margin-bottom: 12px">
              <a-radio value="none">none</a-radio>
              <a-radio value="json">JSON</a-radio>
              <a-radio value="form-data">form-data</a-radio>
              <a-radio value="raw">raw</a-radio>
            </a-radio-group>
            <a-textarea
              v-if="form.body_type !== 'none'"
              v-model:value="bodyContent"
              :rows="6"
              style="font-family: monospace"
            />
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <a-card title="断言配置" style="margin-top: 16px">
        <a-table :data-source="assertions" :columns="assertionColumns" row-key="id" size="small" pagination="false">
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'enabled'">
              <a-checkbox v-model:checked="record.enabled" />
            </template>
            <template v-else-if="column.key === 'assert_type'">
              <a-select v-model:value="record.assert_type" size="small">
                <a-select-option value="status_code">状态码</a-select-option>
                <a-select-option value="response_time">响应时间</a-select-option>
                <a-select-option value="header">响应头</a-select-option>
                <a-select-option value="jsonpath">JSONPath</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
                <a-select-option value="equals">等于</a-select-option>
                <a-select-option value="regex">正则</a-select-option>
                <a-select-option value="script">脚本</a-select-option>
              </a-select>
            </template>
            <template v-else-if="column.key === 'operator'">
              <a-select v-model:value="record.operator" size="small">
                <a-select-option value="equals">等于</a-select-option>
                <a-select-option value="not_equals">不等于</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
                <a-select-option value="not_contains">不包含</a-select-option>
                <a-select-option value="less_than">小于</a-select-option>
                <a-select-option value="greater_than">大于</a-select-option>
                <a-select-option value="matches">匹配</a-select-option>
              </a-select>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" danger size="small" @click="assertions.splice(index, 1)">删除</a-button>
            </template>
          </template>
        </a-table>
        <a-button type="dashed" block style="margin-top: 8px" @click="addAssertion">+ 添加断言</a-button>
      </a-card>

      <a-card title="脚本" style="margin-top: 16px">
        <a-tabs>
          <a-tab-pane tab="前置脚本" key="pre">
            <a-textarea v-model:value="form.pre_script" :rows="6" placeholder="// 请求前执行" style="font-family: monospace" />
          </a-tab-pane>
          <a-tab-pane tab="后置脚本" key="post">
            <a-textarea v-model:value="form.post_script" :rows="6" placeholder="// 响应后执行" style="font-family: monospace" />
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
import { apiCasesApi, apiDefinitionsApi } from '@/api/apiTest'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const caseId = route.params.caseId
const isEdit = computed(() => caseId && caseId !== 'new')

const saving = ref(false)
const activeTab = ref('headers')
const apiList = ref<any[]>([])
const assertions = ref<any[]>([])

const form = ref<any>({
  name: '',
  description: '',
  priority: 'P2',
  method: 'GET',
  path: '',
  api_id: null,
  headers: [],
  query_params: [],
  body_type: 'none',
  body_content: null,
  pre_script: '',
  post_script: '',
  param_source: 'none',
  param_data: null,
})

const bodyContent = computed({
  get: () => typeof form.value.body_content === 'string' ? form.value.body_content : JSON.stringify(form.value.body_content, null, 2),
  set: (val: string) => {
    try { form.value.body_content = JSON.parse(val) } catch { form.value.body_content = val }
  }
})

const paramColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '参数名', dataIndex: 'key', key: 'key' },
  { title: '参数值', dataIndex: 'value', key: 'value' },
  { title: '操作', key: 'action', width: 60 },
]

const assertionColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '类型', key: 'assert_type', width: 120 },
  { title: '目标', dataIndex: 'assert_target', key: 'assert_target' },
  { title: '操作符', key: 'operator', width: 100 },
  { title: '期望值', dataIndex: 'expected_value', key: 'expected_value' },
  { title: '操作', key: 'action', width: 60 },
]

const addAssertion = () => {
  assertions.value.push({
    id: Date.now(),
    assert_type: 'status_code',
    assert_target: '',
    operator: 'equals',
    expected_value: '200',
    enabled: true,
    sort_order: assertions.value.length,
  })
}

const loadApis = async () => {
  try {
    const res = await apiDefinitionsApi.list(projectId, { page_size: 100 })
    apiList.value = res.items
  } catch {}
}

const loadData = async () => {
  if (!isEdit.value) return
  const data = await apiCasesApi.get(projectId, Number(caseId))
  Object.assign(form.value, data)
  try {
    assertions.value = await apiCasesApi.listAssertions(projectId, Number(caseId))
  } catch {}
}

const handleSave = async () => {
  saving.value = true
  try {
    let savedCase: any
    if (isEdit.value) {
      savedCase = await apiCasesApi.update(projectId, Number(caseId), form.value)
    } else {
      savedCase = await apiCasesApi.create(projectId, form.value)
    }
    // 保存断言
    for (const assertion of assertions.value) {
      if (assertion.id && typeof assertion.id === 'number' && assertion.id < 1000000000000) {
        await apiCasesApi.updateAssertion(projectId, assertion.id, assertion)
      } else {
        await apiCasesApi.createAssertion(projectId, savedCase.id, assertion)
      }
    }
    message.success('保存成功')
    router.back()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadApis()
  loadData()
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
