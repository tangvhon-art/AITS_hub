<template>
  <div v-if="task">
    <a-card size="small">
      <a-space style="width: 100%" wrap>
        <span style="font-size: 16px; font-weight: 600">{{ task.name }}</span>
        <a-tag :color="statusColor(task.status)">{{ statusText(task.status) }}</a-tag>
        <a-tag v-if="task.conclusion" :color="conclusionColor(task.conclusion)">{{ conclusionText(task.conclusion) }}</a-tag>
        <div style="flex: 1"></div>
        <a-button v-if="task.status === 'running'" size="small" danger @click="cancel">取消任务</a-button>
        <a-button v-if="task.status === 'completed'" size="small" type="primary" @click="genReport">生成报告</a-button>
        <a-button size="small" @click="goBack">返回</a-button>
      </a-space>
      <a-progress :percent="task.progress" style="margin-top: 12px" />
    </a-card>

    <a-card title="五维模式执行批次" size="small" style="margin-top: 12px">
      <a-table :data-source="runs" row-key="id" size="small" :pagination="false">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="模式" data-index="mode" width="120">
          <template #default="{ text }"><a-tag :color="modeColor(text)">{{ modeText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="状态" data-index="status" width="90">
          <template #default="{ text }"><a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="用例数" data-index="total_cases" width="80" />
        <a-table-column title="通过" data-index="passed_cases" width="80" />
        <a-table-column title="通过率" width="110">
          <template #default="{ record }">{{ record.pass_rate != null ? (record.pass_rate * 100).toFixed(1) + '%' : '-' }}</template>
        </a-table-column>
        <a-table-column title="平均分" width="90">
          <template #default="{ record }">{{ record.score_avg ?? '-' }}</template>
        </a-table-column>
        <a-table-column title="专属指标">
          <template #default="{ record }">
            <span v-if="record.metrics" style="font-size: 12px">
              <a-tag v-for="(v, k) in record.metrics" :key="k" style="margin-bottom: 2px">{{ metricKeyText(k) }}={{ typeof v === 'number' && v <= 1 ? (v * 100).toFixed(0) + '%' : v }}</a-tag>
            </span>
            <span v-else>-</span>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-card title="用例级结果" size="small" style="margin-top: 12px">
      <div class="toolbar">
        <a-select v-model:value="filterMode" style="width: 120px" allow-clear placeholder="全部模式" @change="loadResults">
          <a-select-option v-for="r in runs" :key="r.mode" :value="r.mode">{{ modeText(r.mode) }}</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" style="width: 120px" allow-clear placeholder="全部状态" @change="loadResults">
          <a-select-option value="passed">通过</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
          <a-select-option value="flagged">分歧</a-select-option>
          <a-select-option value="blocked">高危</a-select-option>
        </a-select>
        <a-checkbox v-model:checked="lowScore" @change="loadResults">只看低分(&lt;3.5)</a-checkbox>
        <div style="flex: 1"></div>
        <span>共 {{ resultTotal }} 条</span>
      </div>
      <a-table :data-source="results" row-key="id" :loading="resultLoading" size="small" :pagination="{ pageSize: 10, showTotal: (t: number) => `共 ${t} 条` }" @change="pageChange">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="模式" width="100">
          <template #default="{ record }">{{ modeOf(record) }}</template>
        </a-table-column>
        <a-table-column title="分数" width="90">
          <template #default="{ record }">
            <span :style="{ color: (record.score ?? 0) >= 4 ? '#3f8600' : (record.score ?? 0) >= 3 ? '#cf8a10' : '#cf1322' }">{{ record.score ?? '-' }}</span>
          </template>
        </a-table-column>
        <a-table-column title="状态" data-index="status" width="90">
          <template #default="{ text }"><a-tag :color="resColor(text)">{{ resText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="风险" data-index="risk_level" width="70">
          <template #default="{ text }"><a-tag v-if="text" :color="riskColor(text)">{{ text }}</a-tag><span v-else>-</span></template>
        </a-table-column>
        <a-table-column title="人工分" width="90">
          <template #default="{ record }">{{ record.manual_score ?? '-' }}</template>
        </a-table-column>
        <a-table-column title="操作" width="100">
          <template #default="{ record }"><a-button type="link" size="small" @click="openResult(record)">查看</a-button></template>
        </a-table-column>
      </a-table>
    </a-card>

    <!-- 结果详情 -->
    <a-drawer v-model:open="resultDrawer" title="用例结果详情" width="720">
      <a-descriptions v-if="currentResult" :column="2" size="small" bordered>
        <a-descriptions-item label="综合分">{{ currentResult.score ?? '-' }}</a-descriptions-item>
        <a-descriptions-item label="人工分">{{ currentResult.manual_score ?? '-' }}</a-descriptions-item>
        <a-descriptions-item label="状态">{{ resText(currentResult.status) }}</a-descriptions-item>
        <a-descriptions-item label="风险">{{ currentResult.risk_level || '-' }}</a-descriptions-item>
      </a-descriptions>
      <template v-if="currentResult?.dimension_scores">
        <h4>五维得分</h4>
        <a-space wrap>
          <a-tag v-for="(v, k) in currentResult.dimension_scores" :key="k" color="blue">{{ dimText(k) }}: {{ v }}</a-tag>
        </a-space>
      </template>
      <h4 style="margin-top: 16px">被测模型输出</h4>
      <MdView class="md-body" :content="currentResult?.model_output || '（无输出）'" />
      <template v-if="currentResult?.business_result">
        <h4>业务判定</h4>
        <pre class="out-box">{{ JSON.stringify(currentResult.business_result, null, 2) }}</pre>
      </template>
      <template v-if="currentResult?.judge_scores?.length">
        <h4>多裁判打分</h4>
        <pre class="out-box">{{ JSON.stringify(currentResult.judge_scores, null, 2) }}</pre>
      </template>
      <h4 style="margin-top: 16px">人工复核</h4>
      <a-input-number v-model:value="manualScore" :min="0" :max="5" :step="0.5" style="width: 120px" />
      <a-input v-model:value="manualComment" placeholder="人工评语" style="width: 300px; margin-left: 8px" />
      <a-button type="primary" size="small" style="margin-left: 8px" @click="saveManual">保存人工分</a-button>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import MdView from '@/components/MdView.vue'
import { evalTaskApi, evalResultApi, evalReportApi, EVAL_MODE_TEXT, EVAL_MODE_COLOR } from '@/api/eval'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.taskId)
const task = ref<any>()
const runs = ref<any[]>([])
const results = ref<any[]>([])
const resultLoading = ref(false)
const resultTotal = ref(0)
const filterMode = ref<string>()
const filterStatus = ref<string>()
const lowScore = ref(false)
const resultDrawer = ref(false)
const currentResult = ref<any>()
const manualScore = ref<number>(3)
const manualComment = ref('')
let page = 1
let sse: EventSource | null = null

const modeText = (m: string) => (EVAL_MODE_TEXT as any)[m] || m
const modeColor = (m: string) => (EVAL_MODE_COLOR as any)[m] || 'default'
const statusText = (s: string) => ({ pending: '等待', running: '执行中', completed: '已完成', failed: '失败', canceled: '已取消', ready: '就绪', draft: '草稿' } as any)[s] || s
const statusColor = (s: string) => ({ pending: 'default', running: 'processing', completed: 'success', failed: 'error', canceled: 'warning', ready: 'blue', draft: 'default' } as any)[s] || 'default'
const conclusionText = (c: string) => ({ pass: '准入通过', conditional: '条件通过', reject: '准入驳回' } as any)[c] || c
const conclusionColor = (c: string) => ({ pass: 'green', conditional: 'orange', reject: 'red' } as any)[c] || 'default'
const resText = (s: string) => ({ passed: '通过', failed: '失败', flagged: '分歧', blocked: '高危', pending: '待评' } as any)[s] || s
const resColor = (s: string) => ({ passed: 'success', failed: 'error', flagged: 'warning', blocked: 'red', pending: 'default' } as any)[s] || 'default'
const riskColor = (l: string) => ({ P0: 'red', P1: 'orange', P2: 'gold', P3: 'default' } as any)[l] || 'default'
const dimText = (k: string | number) => ({ accuracy: '事实准确性', relevance: '内容相关性', logic: '逻辑完整性', instruction: '指令遵循度', fluency: '语言流畅度' } as any)[k] || k
const metricKeyText = (k: string | number) => ({
  flagged: '分歧数', flag_count: '分歧数', pass_rate: '通过率', score_avg: '平均分',
  block_rate: '拦截率', blocked: '拦截数', completion_rate: '完成率', success_rate: '成功率',
  closed_tasks: '闭环任务', total_tasks: '任务总数', tool_calls: '工具调用', correct_calls: '调用正确',
  recovered_failures: '纠错成功', total_failures: '失败数', p0_count: 'P0问题', p1_count: 'P1问题',
  jailbreak_success: '越狱成功', jailbreak_failed: '拦截成功',
  total: '总数', passed: '通过数', failed: '失败数', score: '得分',
} as any)[k] || k
const modeOf = (record: any) => {
  const r = runs.value.find((x) => x.id === record.eval_run_id)
  return r ? modeText(r.mode) : '-'
}

const load = async () => {
  task.value = await evalTaskApi.get(taskId)
  runs.value = await evalTaskApi.runs(taskId)
  loadResults()
}
const loadResults = async () => {
  resultLoading.value = true
  try {
    const res: any = await evalTaskApi.results(taskId, {
      mode: filterMode.value, status: filterStatus.value, low_score: lowScore.value || undefined,
      page, page_size: 10,
    })
    results.value = res.items || []
    resultTotal.value = res.total || 0
  } finally { resultLoading.value = false }
}
const pageChange = (p: any) => { page = p.current || 1; loadResults() }

const cancel = async () => { await evalTaskApi.cancel(taskId); message.success('已取消'); load() }
const genReport = async () => { await evalTaskApi.genReport(taskId); message.success('报告生成中，稍后到报告页查看') }
const goBack = () => router.push('/eval/tasks')

const openResult = (record: any) => {
  currentResult.value = record
  manualScore.value = record.manual_score ?? 3
  manualComment.value = record.manual_comment ?? ''
  resultDrawer.value = true
}
const saveManual = async () => {
  await evalResultApi.manualScore(currentResult.value.id, { manual_score: manualScore.value, manual_comment: manualComment.value })
  message.success('人工分已保存'); loadResults()
}

// SSE 实时进度
const openSSE = () => {
  const token = localStorage.getItem('token') || ''
  sse = new EventSource(`/api/eval/tasks/${taskId}/progress?token=${token}`)
  sse.onmessage = (e: any) => {
    try {
      const d = JSON.parse(e.data)
      if (task.value) {
        task.value.progress = d.overall ?? task.value.progress
        task.value.status = d.status ?? task.value.status
        task.value.conclusion = d.conclusion ?? task.value.conclusion
      }
    } catch (err) { /* ignore */ }
  }
  sse.addEventListener('done', () => { load(); sse?.close(); sse = null })
  sse.onerror = () => { sse?.close(); sse = null }
}

onMounted(load)
onMounted(() => {
  const timer = setInterval(() => {
    if (task.value && (task.value.status === 'running' || task.value.status === 'ready')) {
      load()
    } else {
      clearInterval(timer)
    }
  }, 4000)
})
onBeforeUnmount(() => { sse?.close() })
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.out-box { background: #f6f8fa; padding: 12px; border-radius: 6px; max-height: 260px; overflow: auto; white-space: pre-wrap; word-break: break-all; font-size: 12px; }
.md-body { background: #fafafa; padding: 14px 16px; border-radius: 6px; max-height: 320px; overflow: auto; word-break: break-word; font-size: 13px; line-height: 1.7; }
.md-body :deep(pre) { background: #f0f0f0; padding: 10px; border-radius: 6px; overflow: auto; }
.md-body :deep(code) { font-size: 12px; }
.md-body :deep(img) { max-width: 100%; }
h4 { margin: 8px 0; }
</style>
