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
              <a-input v-model:value="form.name" placeholder="请输入用例名称" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item label="优先级">
              <a-select v-model:value="form.priority" placeholder="选择优先级">
                <a-select-option value="P0">P0</a-select-option>
                <a-select-option value="P1">P1</a-select-option>
                <a-select-option value="P2">P2</a-select-option>
                <a-select-option value="P3">P3</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="请求方法">
              <a-select v-model:value="form.method" placeholder="选择方法" :disabled="!!form.api_id">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="PATCH">PATCH</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="关联接口">
              <a-select v-model:value="form.api_id" show-search placeholder="选择接口" allow-clear @change="handleApiChange">
                <a-select-option v-for="api in apiList" :key="api.id" :value="api.id">
                  [{{ api.method }}] {{ api.name }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="用例描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="请输入用例描述" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="测试数据池">
              <a-select
                v-model:value="form.data_pool_id"
                show-search
                allow-clear
                placeholder="选择数据池进行参数化（可选）"
                :filter-option="(input: string, option: any) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())"
                :options="poolOptions"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <a-card title="请求配置" style="margin-top: 16px">
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="headers" tab="Headers">
            <a-table :data-source="form.headers" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="Header名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <div style="display: flex; gap: 4px; align-items: center">
                    <a-input v-model:value="record.value" placeholder="Header值" size="small" style="flex: 1" />
                    <MockDataInserter v-model="record.value" />
                  </div>
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="form.headers.splice(index, 1)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="form.headers.push({ key: '', value: '', enabled: true })">+ 添加</a-button>
          </a-tab-pane>
          <a-tab-pane key="params" tab="Query">
            <a-table :data-source="form.query_params" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="参数名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <div style="display: flex; gap: 4px; align-items: center">
                    <a-input v-model:value="record.value" placeholder="参数值" size="small" style="flex: 1" />
                    <MockDataInserter v-model="record.value" />
                  </div>
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
              <a-radio value="x-www-form-urlencoded">x-www-form-urlencoded</a-radio>
              <a-radio value="raw">raw</a-radio>
              <a-select
                v-if="form.body_type === 'raw'"
                v-model:value="form.raw_language"
                size="small"
                style="width: 120px; margin-left: 8px"
                :options="rawLanguageOptions"
              />
            </a-radio-group>
            <div v-if="form.body_type === 'json' || form.body_type === 'raw'" style="margin-bottom: 8px; display: flex; justify-content: flex-end">
              <MockDataInserter v-model="bodyContent" />
            </div>
            <a-textarea
              v-if="form.body_type === 'json' || form.body_type === 'raw'"
              v-model:value="bodyContent"
              :rows="6"
              placeholder='{"key": "value"}，支持 {{$mock函数}}'
              style="font-family: monospace"
            />
            <a-table
              v-if="form.body_type === 'form-data' || form.body_type === 'x-www-form-urlencoded'"
              :data-source="bodyParams"
              :columns="paramColumns"
              :row-key="(_r: any, index: number) => index"
              size="small"
              pagination="false"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="参数名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <div style="display: flex; gap: 4px; align-items: center">
                    <a-input v-model:value="record.value" placeholder="参数值" size="small" style="flex: 1" />
                    <MockDataInserter v-model="record.value" />
                  </div>
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="bodyParams.splice(index, 1)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button
              v-if="form.body_type === 'form-data' || form.body_type === 'x-www-form-urlencoded'"
              type="dashed"
              block
              style="margin-top: 8px"
              @click="bodyParams.push({ key: '', value: '', enabled: true })"
            >+ 添加字段</a-button>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <a-card title="断言配置" style="margin-top: 16px">
        <a-table :data-source="assertions" :columns="assertionColumns" :row-key="(_r: any, index: number) => index" size="small" pagination="false">
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'enabled'">
              <a-checkbox v-model:checked="record.enabled" />
            </template>
            <template v-else-if="column.key === 'assert_type'">
              <a-select v-model:value="record.assert_type" size="small" placeholder="选择类型">
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
            <template v-else-if="column.key === 'assert_target'">
              <a-input v-model:value="record.assert_target" size="small" :placeholder="getTargetPlaceholder(record.assert_type)" />
            </template>
            <template v-else-if="column.key === 'operator'">
              <a-select v-model:value="record.operator" size="small" placeholder="选择操作符">
                <a-select-option value="equals">等于</a-select-option>
                <a-select-option value="not_equals">不等于</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
                <a-select-option value="not_contains">不包含</a-select-option>
                <a-select-option value="less_than">小于</a-select-option>
                <a-select-option value="greater_than">大于</a-select-option>
                <a-select-option value="matches">匹配</a-select-option>
              </a-select>
            </template>
            <template v-else-if="column.key === 'expected_value'">
              <a-input v-model:value="record.expected_value" size="small" :placeholder="getExpectedPlaceholder(record.assert_type)" />
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
            <div class="script-header">
              <span class="script-tip">支持 JavaScript，可通过 <code>variables.set('key', 'value')</code> 设置变量，<code>variables.get('key')</code> 获取变量</span>
              <a-button size="small" @click="handleAiGenerateScript('pre')" :loading="aiGenerating.pre">
                <template #icon><RobotOutlined /></template>
                AI 生成
              </a-button>
            </div>
            <a-textarea v-model:value="form.pre_script" :rows="6" placeholder="// 请求前执行，例如：&#10;// variables.set('timestamp', Date.now())" style="font-family: monospace" />
          </a-tab-pane>
          <a-tab-pane tab="后置脚本" key="post">
            <div class="script-header">
              <span class="script-tip">支持 JavaScript，可通过 <code>response</code> 访问响应，<code>tests.assert('名称', 条件)</code> 添加断言</span>
              <a-button size="small" @click="handleAiGenerateScript('post')" :loading="aiGenerating.post">
                <template #icon><RobotOutlined /></template>
                AI 生成
              </a-button>
            </div>
            <a-textarea v-model:value="form.post_script" :rows="6" placeholder="// 响应后执行，例如：&#10;// tests.assert('状态码为200', response.statusCode === 200)&#10;// variables.set('user_id', response.body.data.id)" style="font-family: monospace" />
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
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { apiCasesApi, apiDefinitionsApi } from '@/api/apiTest'
import { dataPoolsApi } from '@/api/dataPools'
import MockDataInserter from './MockDataInserter.vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const caseId = route.params.caseId
const isEdit = computed(() => caseId && caseId !== 'new')

const saving = ref(false)
const activeTab = ref('headers')
const apiList = ref<any[]>([])
const assertions = ref<any[]>([])
const aiGenerating = reactive({ pre: false, post: false })
const poolOptions = ref<{ label: string; value: number }[]>([])

async function loadPoolOptions() {
  try {
    const res = await dataPoolsApi.list(projectId, { page: 1, page_size: 100 })
    poolOptions.value = res.items.map((p: any) => ({ label: `${p.name} (${p.data_type})`, value: p.id }))
  } catch { poolOptions.value = [] }
}

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
  raw_language: 'Text',
  pre_script: '',
  post_script: '',
  param_source: 'none',
  param_data: null,
  data_pool_id: null as number | null,
})

const bodyParams = computed({
  get: () => Array.isArray(form.value.body_content) ? form.value.body_content : [],
  set: (val) => { form.value.body_content = val }
})

const bodyContent = computed({
  get: () => {
    if (form.value.body_type === 'raw' && form.value.raw_language !== 'JSON') {
      return typeof form.value.body_content === 'string' ? form.value.body_content : JSON.stringify(form.value.body_content)
    }
    return typeof form.value.body_content === 'string' ? form.value.body_content : JSON.stringify(form.value.body_content, null, 2)
  },
  set: (val: string) => {
    if (form.value.body_type === 'raw' && form.value.raw_language !== 'JSON') {
      form.value.body_content = val
    } else {
      try { form.value.body_content = JSON.parse(val) } catch { form.value.body_content = val }
    }
  }
})

const paramColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '参数名', dataIndex: 'key', key: 'key' },
  { title: '参数值', dataIndex: 'value', key: 'value' },
  { title: '操作', key: 'action', width: 60 },
]

const rawLanguageOptions = [
  { label: 'Text', value: 'Text' },
  { label: 'JavaScript', value: 'JavaScript' },
  { label: 'JSON', value: 'JSON' },
  { label: 'HTML', value: 'HTML' },
  { label: 'XML', value: 'XML' },
]

const assertionColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '类型', key: 'assert_type', width: 120 },
  { title: '目标', dataIndex: 'assert_target', key: 'assert_target' },
  { title: '操作符', key: 'operator', width: 100 },
  { title: '期望值', dataIndex: 'expected_value', key: 'expected_value' },
  { title: '操作', key: 'action', width: 60 },
]

const getTargetPlaceholder = (type: string) => {
  const map: Record<string, string> = {
    status_code: '无需填写',
    response_time: '无需填写',
    header: 'Header 名称，如 Content-Type',
    jsonpath: 'JSONPath，如 $.data.id',
    contains: '响应文本',
    equals: '响应文本',
    regex: '响应文本',
    script: '脚本表达式',
  }
  return map[type] || '断言目标'
}

const getExpectedPlaceholder = (type: string) => {
  const map: Record<string, string> = {
    status_code: '如 200',
    response_time: '如 1000（毫秒）',
    header: '期望的 Header 值',
    jsonpath: '期望的值',
    contains: '期望包含的文本',
    equals: '期望等于的文本',
    regex: '正则表达式',
    script: 'true / false',
  }
  return map[type] || '期望值'
}

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

const handleApiChange = (apiId: number | null) => {
  if (!apiId) return
  const api = apiList.value.find(a => a.id === apiId)
  if (api) {
    form.value.method = api.method
    form.value.path = api.path
    // 保留用户已配置的参数，不覆盖
    if (form.value.headers.length === 0 && api.headers) {
      form.value.headers = api.headers
    }
    if (form.value.query_params.length === 0 && api.query_params) {
      form.value.query_params = api.query_params
    }
    if (form.value.body_type === 'none' && api.body_type && api.body_type !== 'none') {
      form.value.body_type = api.body_type
      form.value.body_content = api.body_content
    }
  }
}

const handleAiGenerateScript = async (type: 'pre' | 'post') => {
  aiGenerating[type] = true
  try {
    // 调用 AI 生成脚本（使用现有 LLM 接口）
    const prompt = type === 'pre'
      ? `请为以下接口测试用例生成前置 JavaScript 脚本：\n用例名称：${form.value.name}\n请求方法：${form.value.method}\n请求路径：${form.value.path}\n\n要求：\n1. 脚本用于请求发送前执行\n2. 可使用 variables.set('key', 'value') 设置变量\n3. 可使用 variables.get('key') 获取变量\n4. 代码简洁，有注释说明`
      : `请为以下接口测试用例生成后置 JavaScript 脚本：\n用例名称：${form.value.name}\n请求方法：${form.value.method}\n请求路径：${form.value.path}\n\n要求：\n1. 脚本用于响应返回后执行\n2. 可使用 response.statusCode、response.body、response.headers 访问响应\n3. 可使用 tests.assert('名称', 条件) 添加测试断言\n4. 可使用 variables.set('key', 'value') 提取响应变量供后续使用\n5. 代码简洁，有注释说明`
    // 这里调用通用 AI 接口，实际项目中替换为真实接口
    message.info('AI 脚本生成功能开发中，请手动编写脚本')
  } finally {
    aiGenerating[type] = false
  }
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
    // 同步 bodyParams 到 body_content
    if (form.value.body_type === 'form-data' || form.value.body_type === 'x-www-form-urlencoded') {
      form.value.body_content = bodyParams.value.filter((p: any) => p.enabled && p.key)
    }
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
  loadPoolOptions()
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
.script-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.script-tip {
  font-size: 12px;
  color: #8c8c8c;
}
.script-tip code {
  background: #f5f5f5;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
</style>
