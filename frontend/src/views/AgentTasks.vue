<template>
  <div class="agent-tasks-page">
    <div class="page-header">
      <h2>Agent 任务监控</h2>
      <a-space>
        <a-select v-model:value="filterAgentType" placeholder="Agent类型" allow-clear style="width: 160px">
          <a-select-option value="case_generator">用例生成</a-select-option>
          <a-select-option value="case_reviewer">用例评审</a-select-option>
          <a-select-option value="ui_execution">UI执行</a-select-option>
          <a-select-option value="defect_analyzer">缺陷分析</a-select-option>
          <a-select-option value="report_generator">报告生成</a-select-option>
          <a-select-option value="bdd_generator">BDD生成</a-select-option>
          <a-select-option value="supervisor">Supervisor</a-select-option>
          <a-select-option value="notification">通知</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px">
          <a-select-option value="running">运行中</a-select-option>
          <a-select-option value="success">成功</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
          <a-select-option value="pending">等待中</a-select-option>
        </a-select>
        <a-button type="primary" @click="loadTasks">查询</a-button>
        <a-button @click="handleReset">重置</a-button>
        <a-button @click="loadTasks">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </a-space>
    </div>

    <!-- Token 统计卡片 -->
    <a-row :gutter="16" class="stats-row" v-if="tokenStats">
      <a-col :span="6">
        <a-card>
          <a-statistic title="总 Token 消耗" :value="tokenStats.total_tokens" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="输入 Token" :value="tokenStats.total_prompt_tokens" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="输出 Token" :value="tokenStats.total_completion_tokens" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="预估成本(USD)" :value="tokenStats.estimated_cost_usd" :precision="4" />
        </a-card>
      </a-col>
    </a-row>

    <a-card>
      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'agent_type'">
            <a-tag color="blue">{{ agentTypeText(record.agent_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'token_usage'">
            <span v-if="record.token_usage?.total_tokens">{{ record.token_usage.total_tokens }}</span>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="viewTask(record)">详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 任务详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="任务详情" :footer="null" width="800px">
      <div v-if="currentTask" class="task-detail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="任务ID">{{ currentTask.id }}</a-descriptions-item>
          <a-descriptions-item label="Agent类型">{{ agentTypeText(currentTask.agent_type) }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(currentTask.status)">{{ statusText(currentTask.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="项目ID">{{ currentTask.project_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ $formatDateTime(currentTask.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="完成时间">{{ currentTask.completed_at || '-' }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>输入参数</a-divider>
        <pre class="json-block">{{ JSON.stringify(currentTask.input_params, null, 2) }}</pre>

        <a-divider v-if="Object.keys(currentTask.output_result || {}).length > 0">输出结果</a-divider>
        <pre class="json-block" v-if="Object.keys(currentTask.output_result || {}).length > 0">{{ JSON.stringify(currentTask.output_result, null, 2) }}</pre>

        <a-divider v-if="currentTask.token_usage && Object.keys(currentTask.token_usage).length > 0">Token 消耗</a-divider>
        <a-descriptions v-if="currentTask.token_usage && Object.keys(currentTask.token_usage).length > 0" :column="3" bordered size="small">
          <a-descriptions-item label="输入 Token">{{ currentTask.token_usage.prompt_tokens || 0 }}</a-descriptions-item>
          <a-descriptions-item label="输出 Token">{{ currentTask.token_usage.completion_tokens || 0 }}</a-descriptions-item>
          <a-descriptions-item label="总 Token">{{ currentTask.token_usage.total_tokens || 0 }}</a-descriptions-item>
        </a-descriptions>

        <a-divider v-if="currentTask.error_message">错误信息</a-divider>
        <a-alert v-if="currentTask.error_message" :message="currentTask.error_message" type="error" show-icon />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAgentTasks, getTokenUsage, type AgentTask, type TokenUsageStats } from '@/api/agentTasks'

const route = useRoute()
const { loadFromUrl, syncToUrl } = useUrlSearch()
const projectId = computed(() => {
  const p = route.params.id ?? route.params.projectId
  const n = Number(p)
  return Number.isFinite(n) ? n : undefined
})

const loading = ref(false)
const tasks = ref<AgentTask[]>([])
const tokenStats = ref<TokenUsageStats | null>(null)
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const filterAgentType = ref<string>()
const filterStatus = ref<string>()

const detailVisible = ref(false)
const currentTask = ref<AgentTask | null>(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: 'Agent类型', dataIndex: 'agent_type', key: 'agent_type', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '项目ID', dataIndex: 'project_id', key: 'project_id', width: 80 },
  { title: 'Token消耗', dataIndex: 'token_usage', key: 'token_usage', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '完成时间', dataIndex: 'completed_at', key: 'completed_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 80, fixed: 'right' as const },
]

async function loadTasks() {
  syncToUrl({ agent_type: filterAgentType.value, status: filterStatus.value })
  loading.value = true
  try {
    const params: any = {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    }
    if (projectId.value) params.project_id = projectId.value
    if (filterAgentType.value) params.agent_type = filterAgentType.value
    if (filterStatus.value) params.status = filterStatus.value

    const res = await getAgentTasks(params)
    tasks.value = res.items
    pagination.value.total = res.total

    // 加载 Token 统计
    if (projectId.value) {
      try {
        const statsRes = await getTokenUsage(projectId.value)
        tokenStats.value = statsRes
      } catch {}
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadTasks()
}

function handleReset() {
  filterAgentType.value = undefined
  filterStatus.value = undefined
  loadTasks()
}

function viewTask(record: AgentTask) {
  currentTask.value = record
  detailVisible.value = true
}

function agentTypeText(t: string) {
  const map: Record<string, string> = {
    case_generator: '用例生成',
    case_reviewer: '用例评审',
    ui_execution: 'UI执行',
    defect_analyzer: '缺陷分析',
    report_generator: '报告生成',
    bdd_generator: 'BDD生成',
    supervisor: 'Supervisor',
    notification: '通知',
  }
  return map[t] || t
}

function statusColor(s: string) {
  const map: Record<string, string> = { pending: 'default', running: 'blue', success: 'green', failed: 'red' }
  return map[s] || 'default'
}
function statusText(s: string) {
  const map: Record<string, string> = { pending: '等待中', running: '运行中', success: '成功', failed: '失败' }
  return map[s] || s
}

onMounted(() => {
  const params = loadFromUrl({ agent_type: undefined, status: undefined })
  filterAgentType.value = params.agent_type
  filterStatus.value = params.status
  if (projectId.value) loadTasks()
})

watch(projectId, (v) => {
  if (v) loadTasks()
})
</script>

<style scoped>
.agent-tasks-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.stats-row { margin-bottom: 16px; }
.task-detail { max-height: 600px; overflow-y: auto; }
.json-block { background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 12px; overflow-x: auto; max-height: 300px; overflow-y: auto; }
</style>
