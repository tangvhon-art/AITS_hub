<template>
  <div>
    <a-alert type="info" show-icon message="人工校准模块" description="对 AI 裁判的低分、争议、高危样本进行人工复核打分，作为自动测评的校准基准。质控标准：抽样 ≥10%、与 AI 裁判相关性 ≥0.8。" style="margin-bottom: 12px" />
    <a-card title="待复核样本队列（低分/分歧/高危）" size="small">
      <a-table :data-source="queue" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="用例ID" data-index="case_id" width="80" />
        <a-table-column title="AI综合分" width="100">
          <template #default="{ record }">
            <span :style="{ color: (record.score ?? 0) < 3.5 ? '#cf1322' : '#cf8a10' }">{{ record.score ?? '-' }}</span>
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
        <a-table-column title="操作" width="90">
          <template #default="{ record }"><a-button type="link" size="small" @click="open(record)">打分</a-button></template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-drawer v-model:open="drawer" title="人工打分复核" width="720">
      <template v-if="current">
        <h4>被测模型输出</h4>
        <MdView class="md-body" :content="current.model_output || '（无输出）'" />
        <template v-if="current.judge_scores?.length">
          <h4>AI 裁判原始打分</h4>
          <pre class="out-box">{{ JSON.stringify(current.judge_scores, null, 2) }}</pre>
        </template>
        <h4>人工评分（1-5）</h4>
        <a-input-number v-model:value="score" :min="1" :max="5" :step="0.5" style="width: 140px" />
        <a-input v-model:value="comment" placeholder="人工评语 / 问题说明" style="width: 320px; margin-left: 8px" />
        <br /><br />
        <a-button type="primary" @click="save">提交人工分</a-button>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import MdView from '@/components/MdView.vue'
import { evalResultApi } from '@/api/eval'

const queue = ref<any[]>([])
const loading = ref(false)
const drawer = ref(false)
const current = ref<any>()
const score = ref(3)
const comment = ref('')

const resText = (s: string) => ({ passed: '通过', failed: '失败', flagged: '分歧', blocked: '高危' } as any)[s] || s
const resColor = (s: string) => ({ passed: 'success', failed: 'error', flagged: 'warning', blocked: 'red' } as any)[s] || 'default'
const riskColor = (l: string) => ({ P0: 'red', P1: 'orange', P2: 'gold', P3: 'default' } as any)[l] || 'default'

const load = async () => {
  loading.value = true
  try { queue.value = await evalResultApi.manualQueue() } finally { loading.value = false }
}
const open = (record: any) => {
  current.value = record
  score.value = record.manual_score ?? 3
  comment.value = record.manual_comment ?? ''
  drawer.value = true
}
const save = async () => {
  await evalResultApi.manualScore(current.value.id, { manual_score: score.value, manual_comment: comment.value, review_status: 'done' })
  message.success('已提交'); drawer.value = false; load()
}
onMounted(load)
</script>

<style scoped>
.out-box { background: #f6f8fa; padding: 12px; border-radius: 6px; max-height: 260px; overflow: auto; white-space: pre-wrap; word-break: break-all; font-size: 12px; }
.md-body { background: #fafafa; padding: 14px 16px; border-radius: 6px; max-height: 320px; overflow: auto; word-break: break-word; font-size: 13px; line-height: 1.7; }
.md-body :deep(pre) { background: #f0f0f0; padding: 10px; border-radius: 6px; overflow: auto; }
.md-body :deep(code) { font-size: 12px; }
.md-body :deep(img) { max-width: 100%; }
h4 { margin: 8px 0; }
</style>
