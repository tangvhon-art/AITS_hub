<template>
  <div class="api-execution-detail">
    <div class="page-header">
      <a-button @click="$router.back()">
        <template #icon><ArrowLeftOutlined /></template>
        返回
      </a-button>
      <h2>执行详情 #{{ executionId }}</h2>
    </div>

    <a-spin :spinning="loading">
      <!-- 执行汇总 -->
      <a-card v-if="execution" title="执行汇总">
        <a-row :gutter="24">
          <a-col :span="6">
            <a-descriptions-item label="状态">
              <a-tag :color="getStatusColor(execution.status)">{{ getStatusName(execution.status) }}</a-tag>
            </a-descriptions-item>
          </a-col>
          <a-col :span="6">
            <a-descriptions-item label="类型">{{ execution.execution_type }}</a-descriptions-item>
          </a-col>
          <a-col :span="6">
            <a-descriptions-item label="名称">{{ execution.ref_name }}</a-descriptions-item>
          </a-col>
          <a-col :span="6">
            <a-descriptions-item label="总耗时">{{ execution.total_duration }}ms</a-descriptions-item>
          </a-col>
        </a-row>
        <a-divider />
        <a-row :gutter="24">
          <a-col :span="4">
            <a-statistic title="总步骤" :value="execution.total_steps" />
          </a-col>
          <a-col :span="4">
            <a-statistic title="通过" :value="execution.passed_steps" :value-style="{ color: '#52c41a' }" />
          </a-col>
          <a-col :span="4">
            <a-statistic title="失败" :value="execution.failed_steps" :value-style="{ color: '#ff4d4f' }" />
          </a-col>
          <a-col :span="4">
            <a-statistic title="跳过" :value="execution.skipped_steps" />
          </a-col>
          <a-col :span="8">
            <a-descriptions-item label="通过率">
              <a-progress :percent="Math.round((execution.pass_rate || 0) * 100)" />
            </a-descriptions-item>
          </a-col>
        </a-row>
        <a-divider v-if="execution.error_message" />
        <a-alert v-if="execution.error_message" type="error" :message="execution.error_message" show-icon />
      </a-card>

      <!-- 步骤结果列表 -->
      <a-card title="步骤结果" style="margin-top: 16px">
        <a-collapse v-model:activeKey="activeKeys">
          <a-collapse-panel
            v-for="(result, index) in results"
            :key="String(result.id || index)"
          >
            <template #header>
              <div class="result-header">
                <span class="result-order">{{ index + 1 }}</span>
                <a-tag :color="getStatusColor(result.status)">{{ getStatusName(result.status) }}</a-tag>
                <span class="result-name">{{ result.step_name }}</span>
                <span v-if="result.request_method" class="result-method">{{ result.request_method }}</span>
                <span class="result-url">{{ result.request_url }}</span>
                <span class="result-time">{{ result.response_time }}ms</span>
              </div>
            </template>

            <div class="result-detail">
              <a-tabs>
                <a-tab-pane key="request" tab="请求">
                  <div v-if="result.request_method">
                    <p><strong>URL:</strong> {{ result.request_url }}</p>
                    <p><strong>Method:</strong> {{ result.request_method }}</p>
                    <p><strong>Headers:</strong></p>
                    <pre class="code-block">{{ formatJson(result.request_headers) }}</pre>
                    <p v-if="result.request_body"><strong>Body:</strong></p>
                    <pre v-if="result.request_body" class="code-block">{{ formatBody(result.request_body) }}</pre>
                  </div>
                </a-tab-pane>
                <a-tab-pane key="response" tab="响应">
                  <p><strong>状态码:</strong> {{ result.response_status }}</p>
                  <p><strong>响应时间:</strong> {{ result.response_time }}ms</p>
                  <p><strong>响应大小:</strong> {{ result.response_size }}B</p>
                  <p><strong>Headers:</strong></p>
                  <pre class="code-block">{{ formatJson(result.response_headers) }}</pre>
                  <p v-if="result.response_body"><strong>Body:</strong></p>
                  <pre v-if="result.response_body" class="code-block">{{ formatBody(result.response_body) }}</pre>
                </a-tab-pane>
                <a-tab-pane key="assertions" tab="断言">
                  <div v-if="result.assertions && result.assertions.length">
                    <div v-for="(assertion, idx) in result.assertions" :key="idx" class="assertion-item">
                      <a-tag :color="assertion.passed ? 'green' : 'red'">{{ assertion.passed ? '通过' : '失败' }}</a-tag>
                      <span>{{ assertion.type }}: {{ assertion.target }} {{ assertion.operator }} {{ assertion.expected }}</span>
                      <span v-if="!assertion.passed" class="assertion-actual">实际: {{ assertion.actual }}</span>
                    </div>
                  </div>
                  <a-empty v-else description="无断言" />
                </a-tab-pane>
                <a-tab-pane key="console" tab="Console">
                  <pre class="console-log">{{ result.console_log || '无输出' }}</pre>
                </a-tab-pane>
                <a-tab-pane key="error" tab="错误" v-if="result.error_message">
                  <a-alert type="error" :message="result.error_message" show-icon />
                </a-tab-pane>
              </a-tabs>
            </div>
          </a-collapse-panel>
        </a-collapse>
        <a-empty v-if="results.length === 0" description="暂无步骤结果" />
      </a-card>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { apiExecutionsApi, type ApiExecution, type ApiExecutionResult } from '@/api/apiTest'

const route = useRoute()
const projectId = Number(route.params.id)
const executionId = Number(route.params.executionId)

const loading = ref(false)
const execution = ref<ApiExecution | null>(null)
const results = ref<ApiExecutionResult[]>([])
const activeKeys = ref<string[]>([])

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    passed: 'green', failed: 'red', partial: 'orange',
    running: 'blue', pending: 'default', skipped: 'default'
  }
  return colors[status] || 'default'
}

const getStatusName = (status: string) => {
  const names: Record<string, string> = {
    passed: '通过', failed: '失败', partial: '部分通过',
    running: '执行中', pending: '等待中', skipped: '跳过'
  }
  return names[status] || status
}

const formatJson = (data: any) => {
  if (!data) return '{}'
  try {
    return JSON.stringify(typeof data === 'string' ? JSON.parse(data) : data, null, 2)
  } catch {
    return String(data)
  }
}

const formatBody = (body: string) => {
  try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
}

const loadData = async () => {
  loading.value = true
  try {
    execution.value = await apiExecutionsApi.get(projectId, executionId)
    results.value = await apiExecutionsApi.getResults(projectId, executionId)
    activeKeys.value = results.value.map((r, i) => String(r.id || i))
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())
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
.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.result-order {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #1890ff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}
.result-name {
  font-weight: 500;
}
.result-method {
  color: #1890ff;
  font-weight: 500;
}
.result-url {
  color: #8c8c8c;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-time {
  color: #8c8c8c;
}
.code-block {
  background: #fafafa;
  padding: 12px;
  border-radius: 4px;
  max-height: 300px;
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
.assertion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.assertion-actual {
  color: #ff4d4f;
  margin-left: 8px;
}
</style>
