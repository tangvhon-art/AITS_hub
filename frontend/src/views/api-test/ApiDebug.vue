<template>
  <div class="api-debug">
    <div class="page-header">
      <h2>接口调试</h2>
      <div class="header-actions">
        <a-select v-model:value="environmentId" placeholder="选择环境" style="width: 160px" allow-clear>
          <a-select-option v-for="env in environments" :key="env.id" :value="env.id">{{ env.name }}</a-select-option>
        </a-select>
        <a-button @click="loadHistory">
          <template #icon><HistoryOutlined /></template>
          历史
        </a-button>
        <a-button type="primary" ghost @click="showSaveModal = true">
          <template #icon><SaveOutlined /></template>
          保存为接口
        </a-button>
      </div>
    </div>

    <a-card>
      <!-- 请求行 -->
      <div class="request-line">
        <a-select v-model:value="request.method" style="width: 100px" placeholder="方法">
          <a-select-option value="GET">GET</a-select-option>
          <a-select-option value="POST">POST</a-select-option>
          <a-select-option value="PUT">PUT</a-select-option>
          <a-select-option value="DELETE">DELETE</a-select-option>
          <a-select-option value="PATCH">PATCH</a-select-option>
        </a-select>
        <a-input v-model:value="request.url" placeholder="输入请求URL，支持 {{变量}} 和 {{$mock函数}}">
          <template #addonAfter>
            <MockDataInserter v-model="request.url" />
          </template>
        </a-input>
        <a-button type="primary" :loading="sending" @click="handleSend">发送</a-button>
      </div>
      <div v-if="fullUrl" class="url-preview">
        完整请求地址：<span class="url-text">{{ fullUrl }}</span>
      </div>

      <!-- 请求配置 Tab -->
      <a-tabs v-model:activeKey="activeTab" style="margin-top: 16px">
        <a-tab-pane key="params" tab="Params">
          <a-table :data-source="request.query_params" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" :pagination="false">
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
                <a-button type="link" danger size="small" @click="request.query_params.splice(index, 1)">删除</a-button>
              </template>
            </template>
          </a-table>
          <a-button type="dashed" block style="margin-top: 8px" @click="request.query_params.push({ key: '', value: '', enabled: true })">+ 添加参数</a-button>
        </a-tab-pane>
        <a-tab-pane key="headers" tab="Headers">
          <a-table :data-source="request.headers" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" :pagination="false">
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
                <a-button type="link" danger size="small" @click="request.headers.splice(index, 1)">删除</a-button>
              </template>
            </template>
          </a-table>
          <a-button type="dashed" block style="margin-top: 8px" @click="request.headers.push({ key: '', value: '', enabled: true })">+ 添加 Header</a-button>
        </a-tab-pane>
        <a-tab-pane key="body" tab="Body">
          <a-radio-group v-model:value="request.body_type" style="margin-bottom: 12px">
            <a-radio value="none">none</a-radio>
            <a-radio value="json">JSON</a-radio>
            <a-radio value="form-data">form-data</a-radio>
            <a-radio value="x-www-form-urlencoded">x-www-form-urlencoded</a-radio>
            <a-radio value="raw">raw</a-radio>
          </a-radio-group>
          <div v-if="request.body_type === 'json' || request.body_type === 'raw'" style="margin-bottom: 8px; display: flex; justify-content: flex-end">
            <MockDataInserter v-model="bodyContent" />
          </div>
          <a-textarea
            v-if="request.body_type === 'json' || request.body_type === 'raw'"
            v-model:value="bodyContent"
            :rows="8"
            placeholder='{"key": "value"}，支持 {{$mock函数}}'
            style="font-family: monospace"
          />
          <a-table
            v-if="request.body_type === 'form-data' || request.body_type === 'x-www-form-urlencoded'"
            :data-source="bodyParams"
            :columns="paramColumns"
            :row-key="(_r: any, index: number) => index"
            size="small"
            :pagination="false"
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
            v-if="request.body_type === 'form-data' || request.body_type === 'x-www-form-urlencoded'"
            type="dashed"
            block
            style="margin-top: 8px"
            @click="bodyParams.push({ key: '', value: '', enabled: true })"
          >+ 添加字段</a-button>
        </a-tab-pane>
        <a-tab-pane key="pre-script" tab="Pre-request">
          <a-textarea v-model:value="request.pre_script" :rows="8" placeholder="// 请求前执行的脚本" style="font-family: monospace" />
        </a-tab-pane>
        <a-tab-pane key="tests" tab="Tests">
          <a-textarea v-model:value="request.post_script" :rows="8" placeholder="// 响应后执行的测试脚本" style="font-family: monospace" />
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 响应区域 -->
    <a-card v-if="response" title="响应" style="margin-top: 16px">
      <div class="response-status">
        <a-tag :color="response.status_code < 400 ? 'green' : 'red'">{{ response.status_code }}</a-tag>
        <span>{{ response.response_time }}ms</span>
        <span>{{ formatSize(response.response_size) }}</span>
      </div>
      <a-tabs v-model:activeKey="responseTab">
        <a-tab-pane key="body" tab="Body">
          <pre class="response-body">{{ formatBody(response.response_body) }}</pre>
        </a-tab-pane>
        <a-tab-pane key="headers" tab="Headers">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item v-for="(value, key) in response.response_headers" :key="key" :label="key">
              {{ value }}
            </a-descriptions-item>
          </a-descriptions>
        </a-tab-pane>
        <a-tab-pane key="tests" tab="Test Results">
          <div v-if="response.tests && response.tests.length">
            <div v-for="(test, idx) in response.tests" :key="idx" class="test-item">
              <a-tag :color="test.passed ? 'green' : 'red'">{{ test.passed ? '通过' : '失败' }}</a-tag>
              <span>{{ test.name }}</span>
            </div>
          </div>
          <a-empty v-else description="无测试结果" />
        </a-tab-pane>
        <a-tab-pane key="console" tab="Console">
          <pre class="console-log">{{ response.console_log || '无输出' }}</pre>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 历史记录抽屉 -->
    <a-drawer v-model:open="showHistory" title="调试历史" width="400px">
      <a-list :data-source="historyList" item-layout="horizontal">
        <template #renderItem="{ item }">
          <a-list-item @click="loadFromHistory(item)" style="cursor: pointer">
            <a-list-item-meta>
              <template #title>
                <a-tag :color="getMethodColor(item.method)" style="margin-right: 8px">{{ item.method }}</a-tag>
                {{ item.url }}
              </template>
              <template #description>
                {{ item.response_status }} · {{ item.response_time }}ms · {{ formatDateTime(item.created_at) }}
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-drawer>

    <!-- 保存为接口弹窗 -->
    <a-modal v-model:open="showSaveModal" title="保存为接口" @ok="handleSaveAsApi" :confirm-loading="saving">
      <a-form layout="vertical">
        <a-form-item label="接口名称" required>
          <a-input v-model:value="saveForm.name" placeholder="输入接口名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="saveForm.description" placeholder="输入接口描述（可选）" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { HistoryOutlined, SaveOutlined } from '@ant-design/icons-vue'
import { apiDebugApi, apiDefinitionsApi } from '@/api/apiTest'
import { getEnvironments } from '@/api/environments'
import { formatDateTime } from '@/utils/date'
import MockDataInserter from './MockDataInserter.vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const sending = ref(false)
const activeTab = ref('params')
const responseTab = ref('body')
const environmentId = ref<number | null>(null)
const environments = ref<any[]>([])
const response = ref<any>(null)
const showHistory = ref(false)
const historyList = ref<any[]>([])
const showSaveModal = ref(false)
const saving = ref(false)
const saveForm = ref({ name: '', description: '' })

const request = ref<any>({
  method: 'GET',
  url: '',
  headers: [],
  query_params: [],
  body_type: 'none',
  body_content: null,
  pre_script: '',
  post_script: '',
  timeout: 30,
})

const bodyParams = ref<any[]>([])

const syncBodyContent = () => {
  if (request.value.body_type === 'form-data' || request.value.body_type === 'x-www-form-urlencoded') {
    request.value.body_content = bodyParams.value.filter((p: any) => p.enabled && p.key)
  }
}

watch(() => request.value.body_type, (type) => {
  if (type === 'form-data' || type === 'x-www-form-urlencoded') {
    if (Array.isArray(request.value.body_content)) {
      bodyParams.value = request.value.body_content
    } else {
      bodyParams.value = []
    }
  }
})

const bodyContent = computed({
  get: () => typeof request.value.body_content === 'string' ? request.value.body_content : JSON.stringify(request.value.body_content, null, 2),
  set: (val: string) => {
    try { request.value.body_content = JSON.parse(val) } catch { request.value.body_content = val }
  }
})

const paramColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '参数名', dataIndex: 'key', key: 'key' },
  { title: '参数值', dataIndex: 'value', key: 'value' },
  { title: '操作', key: 'action', width: 60 },
]

const fullUrl = computed(() => {
  const inputUrl = request.value.url?.trim() || ''
  if (!inputUrl) return ''
  if (inputUrl.startsWith('http://') || inputUrl.startsWith('https://')) {
    return inputUrl
  }
  const env = environments.value.find(e => e.id === environmentId.value)
  if (env?.base_url) {
    const base = env.base_url.endsWith('/') ? env.base_url.slice(0, -1) : env.base_url
    const path = inputUrl.startsWith('/') ? inputUrl.slice(1) : inputUrl
    return base + '/' + path
  }
  return inputUrl
})

const getMethodColor = (method: string) => {
  const colors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }
  return colors[method] || 'default'
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

const formatBody = (body: string) => {
  try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
}

const handleSend = async () => {
  if (!request.value.url) {
    message.warning('请输入请求URL')
    return
  }
  syncBodyContent()
  sending.value = true
  response.value = null
  try {
    const res = await apiDebugApi.send(projectId, {
      ...request.value,
      environment_id: environmentId.value,
    })
    response.value = res
  } finally {
    sending.value = false
  }
}

const loadHistory = async () => {
  showHistory.value = true
  try {
    historyList.value = await apiDebugApi.history(projectId, 50)
  } catch {}
}

const loadFromHistory = (item: any) => {
  request.value.method = item.method
  request.value.url = item.url
  if (item.request_config) {
    Object.assign(request.value, item.request_config)
    if ((item.request_config.body_type === 'form-data' || item.request_config.body_type === 'x-www-form-urlencoded')
        && Array.isArray(item.request_config.body_content)) {
      bodyParams.value = item.request_config.body_content
    }
  }
  showHistory.value = false
}

const loadApiFromQuery = async () => {
  const apiId = route.query.api_id
  if (apiId) {
    try {
      const api = await apiDefinitionsApi.get(projectId, Number(apiId))
      request.value.method = api.method
      request.value.url = api.path
      request.value.headers = api.headers || []
      request.value.query_params = api.query_params || []
      request.value.body_type = api.body_type
      request.value.body_content = api.body_content
      if ((api.body_type === 'form-data' || api.body_type === 'x-www-form-urlencoded')
          && Array.isArray(api.body_content)) {
        bodyParams.value = api.body_content
      }
    } catch {}
  }
}

const handleSaveAsApi = async () => {
  if (!saveForm.value.name) {
    message.warning('请输入接口名称')
    return
  }
  if (!request.value.url) {
    message.warning('请先填写请求URL')
    return
  }
  syncBodyContent()
  saving.value = true
  try {
    // 提取路径部分，去掉域名
    let apiPath = request.value.url
    try {
      const urlObj = new URL(request.value.url)
      apiPath = urlObj.pathname + urlObj.search
    } catch {
      // 如果不是完整URL，保持原样
    }
    const created = await apiDefinitionsApi.create(projectId, {
      name: saveForm.value.name,
      description: saveForm.value.description,
      method: request.value.method,
      path: apiPath,
      headers: request.value.headers,
      query_params: request.value.query_params,
      body_type: request.value.body_type,
      body_content: request.value.body_content,
      status: 'active',
    })
    message.success(`接口「${saveForm.value.name}」已保存`)
    showSaveModal.value = false
    saveForm.value = { name: '', description: '' }
    // 跳转到接口编辑页
    router.push(`/projects/${projectId}/api-test/definitions/${created.id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadApiFromQuery()
  getEnvironments(projectId).then(data => { environments.value = data }).catch(() => {})
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
.header-actions {
  display: flex;
  gap: 8px;
}
.request-line {
  display: flex;
  gap: 8px;
}
.url-preview {
  margin-top: 8px;
  padding: 6px 12px;
  background: #f6f8fa;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
}
.url-preview .url-text {
  color: #1677ff;
  font-family: monospace;
  word-break: break-all;
}
.response-status {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  align-items: center;
}
.response-body {
  background: #fafafa;
  padding: 12px;
  border-radius: 4px;
  max-height: 400px;
  overflow: auto;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
.console-log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  max-height: 300px;
  overflow: auto;
  font-family: monospace;
  font-size: 12px;
}
.test-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
</style>
