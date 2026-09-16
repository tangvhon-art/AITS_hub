<template>
  <div>
    <a-card title="版本对比" size="small">
      <div class="toolbar">
        <span>当前任务：</span>
        <a-select v-model:value="taskId" style="width: 260px" placeholder="选择已完成的测评任务" @change="load">
          <a-select-option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
        </a-select>
        <span style="margin-left: 16px">对比基准：</span>
        <a-select v-model:value="compareTaskId" style="width: 260px" allow-clear placeholder="默认同被测对象最近任务" @change="load">
          <a-select-option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
        </a-select>
        <a-button type="primary" @click="load">对比</a-button>
      </div>

      <a-spin :spinning="loading">
        <div v-if="result">
          <h4>当前任务 #{{ result.current_task }} vs 基准任务 #{{ result.base_task || '-' }}</h4>
          <a-table :data-source="tableData" row-key="mode" size="small" :pagination="false">
            <a-table-column title="维度" data-index="mode" width="140">
              <template #default="{ text }"><a-tag :color="modeColor(text)">{{ modeText(text) }}</a-tag></template>
            </a-table-column>
            <a-table-column title="当前版本" data-index="current" width="220">
              <template #default="{ record }">{{ fmt(record.cur) }}</template>
            </a-table-column>
            <a-table-column title="基准版本" data-index="base" width="220">
              <template #default="{ record }">{{ fmt(record.base) }}</template>
            </a-table-column>
            <a-table-column title="差异" data-index="diff">
              <template #default="{ record }">
                <a-tag v-if="record.score_diff != null" :color="record.score_diff >= 0 ? 'green' : 'red'">
                  {{ record.score_diff >= 0 ? '+' : '' }}{{ record.score_diff }}
                </a-tag>
                <span v-else>-</span>
              </template>
            </a-table-column>
          </a-table>
        </div>
        <a-empty v-else-if="!loading" description="选择任务后对比" />
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { evalTaskApi, EVAL_MODE_TEXT, EVAL_MODE_COLOR } from '@/api/eval'

const tasks = ref<any[]>([])
const taskId = ref<number>()
const compareTaskId = ref<number>()
const result = ref<any>()
const loading = ref(false)

const modeText = (m: string) => (EVAL_MODE_TEXT as any)[m] || m
const modeColor = (m: string) => (EVAL_MODE_COLOR as any)[m] || 'default'

const fmt = (obj: any) => {
  if (!obj) return '-'
  const parts: string[] = []
  if (obj.score != null) parts.push(`分:${obj.score}`)
  if (obj.score_avg != null) parts.push(`平均分:${obj.score_avg}`)
  if (obj.pass_rate != null) parts.push(`通过率:${(obj.pass_rate * 100).toFixed(0)}%`)
  if (obj.success_rate != null) parts.push(`成功率:${(obj.success_rate * 100).toFixed(0)}%`)
  if (obj.completion_rate != null) parts.push(`完成率:${(obj.completion_rate * 100).toFixed(0)}%`)
  if (obj.block_rate != null) parts.push(`拦截率:${(obj.block_rate * 100).toFixed(0)}%`)
  if (obj.flagged != null) parts.push(`分歧:${obj.flagged}`)
  if (obj.p0_count != null) parts.push(`P0:${obj.p0_count}`)
  return parts.length ? parts.join('，') : '-'
}

const tableData = computed(() => {
  const diff = result.value?.diff || {}
  return Object.entries(diff).map(([mode, v]: [string, any]) => ({
    mode, cur: v?.current, base: v?.base, score_diff: v?.score_diff,
  }))
})

const load = async () => {
  if (!taskId.value) return
  loading.value = true
  try {
    result.value = await evalTaskApi.compare(taskId.value, compareTaskId.value || undefined)
  } finally { loading.value = false }
}

onMounted(async () => {
  tasks.value = (await evalTaskApi.list({ status: 'completed' })).filter((t: any) => t.summary)
})
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
h4 { margin: 8px 0 12px; }
</style>
