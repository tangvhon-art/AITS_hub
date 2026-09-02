<template>
  <div>
    <a-card size="small">
      <div class="toolbar">
        <a-select v-model:value="filterStatus" style="width: 140px" allow-clear placeholder="全部状态" @change="load">
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="ready">就绪</a-select-option>
          <a-select-option value="running">执行中</a-select-option>
          <a-select-option value="completed">已完成</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
        <a-input v-model:value="keyword" placeholder="搜索任务名" style="width: 180px" @pressEnter="load" />
        <a-button @click="load">搜索</a-button>
        <div style="flex: 1"></div>
        <a-button type="primary" @click="openCreate"><PlusOutlined /> 新建测评任务</a-button>
      </div>
      <a-table :data-source="list" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="任务名称" data-index="name" ellipsis />
        <a-table-column title="被测对象" width="160">
          <template #default="{ record }">{{ targetName(record.target_id) }}</template>
        </a-table-column>
        <a-table-column title="模式" width="180">
          <template #default="{ record }">
            <a-tag v-for="m in modeList(record)" :key="m" :color="modeColor(m)" style="margin-bottom: 2px">{{ modeText(m) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="状态" data-index="status" width="90">
          <template #default="{ text }"><a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="进度" width="130">
          <template #default="{ record }"><a-progress :percent="record.progress" :size="24" /></template>
        </a-table-column>
        <a-table-column title="结论" data-index="conclusion" width="100">
          <template #default="{ text }">
            <a-tag v-if="text" :color="conclusionColor(text)">{{ conclusionText(text) }}</a-tag>
            <span v-else>-</span>
          </template>
        </a-table-column>
        <a-table-column title="操作" width="220">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="goDetail(record)">详情</a-button>
              <a-button v-if="record.status === 'ready' || record.status === 'draft'" type="link" size="small" @click="runTask(record)">启动</a-button>
              <a-button v-if="record.status === 'running'" type="link" danger size="small" @click="cancelTask(record)">取消</a-button>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <!-- 新建任务 -->
    <a-modal v-model:open="createOpen" title="新建测评任务" @ok="createTask" :confirm-loading="saving" width="720" ok-text="创建并就绪">
      <a-form :model="form" layout="vertical">
        <a-form-item label="任务名称" required><a-input v-model:value="form.name" placeholder="如 Qwen3.5-4B 五维测评 v0.1" /></a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="被测对象" required>
              <a-select v-model:value="form.target_id" placeholder="选择被测对象">
                <a-select-option v-for="t in targets" :key="t.id" :value="t.id">{{ t.name }}（{{ typeText(t.target_type) }}）</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="对比对象（版本对比可选）">
              <a-select v-model:value="form.compare_target_id" allow-clear placeholder="不对比">
                <a-select-option v-for="t in targets" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="裁判模型（AI裁判打分，可多选）">
          <a-select v-model:value="form.judge_config_ids" mode="multiple" allow-clear placeholder="默认取活跃模型前 2 个">
            <a-select-option v-for="c in llmConfigs" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="五维模式与数据集" required>
          <div v-for="m in modeOptions" :key="m.value" class="mode-row">
            <a-checkbox v-model:checked="modeEnabled[m.value]">{{ m.label }}</a-checkbox>
            <a-select
              v-if="modeEnabled[m.value]"
              v-model:value="form.dataset_ids[m.value]"
              mode="multiple"
              placeholder="选择数据集"
              style="width: 100%; margin-top: 6px"
            >
              <a-select-option v-for="ds in datasetsByType(m.value)" :key="ds.id" :value="ds.id">{{ ds.name }}</a-select-option>
            </a-select>
          </div>
        </a-form-item>
        <a-form-item label="执行后端">
          <a-radio-group v-model:value="form.backend">
            <a-radio value="local">默认内部 Agent（local）</a-radio>
            <a-radio value="workflow" disabled>外部工作流（M5 预留）</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { evalTargetApi, evalDatasetApi, evalTaskApi, EVAL_MODE_TEXT, EVAL_MODE_COLOR, EVAL_TYPE_TEXT } from '@/api/eval'
import { getLLMConfigs } from '@/api/llm'

const router = useRouter()
const list = ref<any[]>([])
const targets = ref<any[]>([])
const datasets = ref<any[]>([])
const llmConfigs = ref<any[]>([])
const loading = ref(false)
const filterStatus = ref<string>()
const keyword = ref('')
const createOpen = ref(false)
const saving = ref(false)
const form = ref<any>({ name: '', target_id: undefined, compare_target_id: undefined, judge_config_ids: [], dataset_ids: {}, backend: 'local' })
const modeEnabled = ref<Record<string, boolean>>({ ai_judge: true, manual: false, agent: false, business: false, redteam: false })

const modeOptions = [
  { value: 'ai_judge', label: 'AI裁判（自动批量打分）' },
  { value: 'agent', label: 'Agent交互（多轮/工具）' },
  { value: 'business', label: '业务落地（黄金用例）' },
  { value: 'redteam', label: '对抗红队（安全兜底）' },
  { value: 'manual', label: '人工（抽样校准）' },
]
const modeText = (m: string) => (EVAL_MODE_TEXT as any)[m] || m
const modeColor = (m: string) => (EVAL_MODE_COLOR as any)[m] || 'default'
const typeText = (t: string) => (EVAL_TYPE_TEXT as any)[t] || t
const statusText = (s: string) => ({ draft: '草稿', ready: '就绪', running: '执行中', completed: '已完成', failed: '失败', canceled: '已取消' } as any)[s] || s
const statusColor = (s: string) => ({ draft: 'default', ready: 'blue', running: 'processing', completed: 'success', failed: 'error', canceled: 'warning' } as any)[s] || 'default'
const conclusionText = (c: string) => ({ pass: '准入通过', conditional: '条件通过', reject: '准入驳回' } as any)[c] || c
const conclusionColor = (c: string) => ({ pass: 'green', conditional: 'orange', reject: 'red' } as any)[c] || 'default'

const modeList = (record: any) => Object.keys(record.dataset_ids || {}).filter((m: any) => (record.dataset_ids || {})[m]?.length)
const targetName = (id: number) => targets.value.find((t) => t.id === id)?.name || `#${id}`
const datasetsByType = (type: string) => datasets.value.filter((d) => d.eval_type === type)

const load = async () => {
  loading.value = true
  try {
    list.value = await evalTaskApi.list({ status: filterStatus.value, keyword: keyword.value })
  } finally { loading.value = false }
}

const openCreate = async () => {
  targets.value = await evalTargetApi.list()
  datasets.value = await evalDatasetApi.list()
  createOpen.value = true
}

const createTask = async () => {
  if (!form.value.name) { message.warning('请填写任务名称'); return }
  if (!form.value.target_id) { message.warning('请选择被测对象'); return }
  const dataset_ids: Record<string, number[]> = {}
  for (const m of modeOptions) {
    if (modeEnabled.value[m.value] && (form.value.dataset_ids[m.value] || []).length) {
      dataset_ids[m.value] = form.value.dataset_ids[m.value]
    }
  }
  if (!Object.keys(dataset_ids).length) { message.warning('请至少选择一个模式并配置数据集'); return }
  const modes: Record<string, any> = {}
  Object.keys(dataset_ids).forEach((m) => { modes[m] = { datasets: dataset_ids[m] } })
  saving.value = true
  try {
    await evalTaskApi.create({ ...form.value, modes, dataset_ids })
    message.success('测评任务已创建')
    createOpen.value = false
    load()
  } finally { saving.value = false }
}

const runTask = async (record: any) => {
  await evalTaskApi.run(record.id)
  message.success('测评已提交到 eval 队列')
  setTimeout(load, 1500)
}
const cancelTask = async (record: any) => {
  await evalTaskApi.cancel(record.id)
  message.success('任务已取消'); load()
}
const goDetail = (record: any) => router.push(`/eval/tasks/${record.id}`)

onMounted(async () => {
  try { llmConfigs.value = await getLLMConfigs() } catch (e) { /* 忽略 */ }
})
onMounted(async () => {
  load()
  try { targets.value = await evalTargetApi.list() } catch (e) { /* 忽略 */ }
})
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.mode-row { margin-bottom: 10px; }
</style>
