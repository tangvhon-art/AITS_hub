<template>
  <div>
    <a-alert type="warning" show-icon message="对抗红队测评" description="主动构造越狱、提示注入、隐私探测、偏见诱导等高危用例。P0（越狱成功/违规输出/隐私泄露）零容忍，必须修复后才可上线。" style="margin-bottom: 12px" />
    <a-card title="发起红队专项" size="small" style="margin-bottom: 12px">
      <a-space wrap>
        <span>攻击数据集：</span>
        <a-select v-model:value="dataset_id" style="width: 260px" placeholder="选择红队数据集">
          <a-select-option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.name }}（{{ d.case_count }} 条）</a-select-option>
        </a-select>
        <span>被测对象：</span>
        <a-select v-model:value="target_id" style="width: 200px" allow-clear placeholder="默认第一个模型/Agent">
          <a-select-option v-for="t in targets" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
        </a-select>
        <a-button type="primary" :loading="running" @click="run">启动红队攻击</a-button>
      </a-space>
    </a-card>

    <a-card title="红队攻击日志" size="small">
      <div class="toolbar">
        <a-select v-model:value="filterRisk" style="width: 120px" allow-clear placeholder="全部风险" @change="loadLogs">
          <a-select-option value="P0">P0</a-select-option>
          <a-select-option value="P1">P1</a-select-option>
          <a-select-option value="P2">P2</a-select-option>
          <a-select-option value="P3">P3</a-select-option>
        </a-select>
        <div style="flex: 1"></div>
        <a-button @click="loadLogs">刷新</a-button>
      </div>
      <a-table :data-source="logs" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10, showTotal: (t: number) => `共 ${t} 条` }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="用例ID" data-index="case_id" width="80" />
        <a-table-column title="攻击结果" data-index="redteam_result" width="100">
          <template #default="{ text }">
            <a-tag :color="text === 'blocked' ? 'green' : 'red'">{{ text === 'blocked' ? '已拦截' : '放行(风险)' }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="风险定级" data-index="risk_level" width="90">
          <template #default="{ text }"><a-tag v-if="text" :color="riskColor(text)">{{ text }}</a-tag><span v-else>-</span></template>
        </a-table-column>
        <a-table-column title="操作" width="90">
          <template #default="{ record }"><a-button type="link" size="small" @click="view(record)">查看</a-button></template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-drawer v-model:open="drawer" title="攻击记录详情" width="680">
      <template v-if="current">
        <h4>攻击载荷用例 #{{ current.case_id }}</h4>
        <h4>模型输出</h4>
        <div class="md-body" v-html="renderMd(current.model_output || '（无输出）')"></div>
        <h4>判定</h4>
        <pre class="out-box">{{ JSON.stringify({ result: current.redteam_result, risk_level: current.risk_level }, null, 2) }}</pre>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import { evalRedteamApi, evalTargetApi, evalDatasetApi } from '@/api/eval'

const datasets = ref<any[]>([])
const targets = ref<any[]>([])
const dataset_id = ref<number>()
const target_id = ref<number>()
const running = ref(false)
const logs = ref<any[]>([])
const loading = ref(false)
const filterRisk = ref<string>()
const drawer = ref(false)
const current = ref<any>()

const riskColor = (l: string) => ({ P0: 'red', P1: 'orange', P2: 'gold', P3: 'default' } as any)[l] || 'default'
const renderMd = (text?: string) => {
  if (!text) return ''
  try { return marked.parse(text) as string } catch { return text }
}

const run = async () => {
  if (!dataset_id.value) { message.warning('请选择攻击数据集'); return }
  running.value = true
  try {
    const res: any = await evalRedteamApi.run({ dataset_id: dataset_id.value, target_id: target_id.value })
    message.success(`红队专项已启动，任务 #${res.task_id}`)
    setTimeout(loadLogs, 2000)
  } finally { running.value = false }
}
const loadLogs = async () => {
  loading.value = true
  try {
    const res: any = await evalRedteamApi.logs({ risk_level: filterRisk.value, page: 1, page_size: 20 })
    logs.value = res.items || []
  } finally { loading.value = false }
}
const view = (record: any) => { current.value = record; drawer.value = true }

onMounted(async () => {
  targets.value = await evalTargetApi.list()
  datasets.value = (await evalDatasetApi.list()).filter((d: any) => d.eval_type === 'redteam')
  loadLogs()
})
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
