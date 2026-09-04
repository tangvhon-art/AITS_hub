<template>
  <div>
    <a-card title="测评报告" size="small">
      <div class="toolbar">
        <a-select v-model:value="filterTask" style="width: 170px" allow-clear placeholder="全部任务">
          <a-select-option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
        </a-select>
        <a-input v-model:value="keyword" placeholder="报告标题" style="width: 160px" @pressEnter="load" />
        <a-select v-model:value="filterType" style="width: 100px" allow-clear placeholder="全部类型">
          <a-select-option value="overall">总报告</a-select-option>
          <a-select-option value="ai_judge">AI裁判</a-select-option>
          <a-select-option value="manual">人工</a-select-option>
          <a-select-option value="agent">Agent</a-select-option>
          <a-select-option value="business">业务</a-select-option>
          <a-select-option value="redteam">红队</a-select-option>
        </a-select>
        <a-select v-model:value="filterConclusion" style="width: 100px" allow-clear placeholder="全部结论">
          <a-select-option value="pass">准入通过</a-select-option>
          <a-select-option value="conditional">条件通过</a-select-option>
          <a-select-option value="reject">准入驳回</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" style="width: 100px" allow-clear placeholder="全部状态">
          <a-select-option value="completed">已完成</a-select-option>
          <a-select-option value="generating">生成中</a-select-option>
        </a-select>
        <a-button type="primary" @click="load">查询</a-button>
        <a-button @click="reset">重置</a-button>
        <div style="flex: 1"></div>
      </div>
      <a-table :data-source="list" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="报告标题" data-index="title" ellipsis />
        <a-table-column title="类型" data-index="report_type" width="100">
          <template #default="{ text }"><a-tag :color="typeColor(text)">{{ typeText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="结论" data-index="conclusion" width="100">
          <template #default="{ text }"><a-tag v-if="text" :color="conclusionColor(text)">{{ conclusionText(text) }}</a-tag><span v-else>-</span></template>
        </a-table-column>
        <a-table-column title="状态" data-index="status" width="90">
          <template #default="{ text }"><a-tag :color="text === 'completed' ? 'green' : 'orange'">{{ text === 'completed' ? '已完成' : '生成中' }}</a-tag></template>
        </a-table-column>
        <a-table-column title="创建时间" data-index="created_at" width="180" />
        <a-table-column title="操作" width="90">
          <template #default="{ record }"><a-button type="link" size="small" @click="view(record)">查看</a-button></template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-modal v-model:open="detailOpen" :title="current?.title || '报告'" width="900" footer="null">
      <MdView v-if="current?.content" :content="current.content" />
      <a-empty v-else description="暂无内容" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import MdView from '@/components/MdView.vue'
import { evalReportApi, evalTaskApi } from '@/api/eval'

const list = ref<any[]>([])
const tasks = ref<any[]>([])
const loading = ref(false)
const filterTask = ref<number>()
const keyword = ref('')
const filterType = ref<string>()
const filterConclusion = ref<string>()
const filterStatus = ref<string>()
const detailOpen = ref(false)
const current = ref<any>()

const typeText = (t: string) => ({ overall: '总报告', ai_judge: 'AI裁判', manual: '人工', agent: 'Agent', business: '业务', redteam: '红队' } as any)[t] || t
const typeColor = (t: string) => ({ overall: 'blue', redteam: 'red', manual: 'purple', agent: 'cyan', business: 'green' } as any)[t] || 'default'
const conclusionText = (c: string) => ({ pass: '准入通过', conditional: '条件通过', reject: '准入驳回' } as any)[c] || c
const conclusionColor = (c: string) => ({ pass: 'green', conditional: 'orange', reject: 'red' } as any)[c] || 'default'

const load = async () => {
  loading.value = true
  try {
    list.value = await evalReportApi.list({
      task_id: filterTask.value,
      title: keyword.value || undefined,
      report_type: filterType.value,
      conclusion: filterConclusion.value,
      status: filterStatus.value,
    })
  } finally { loading.value = false }
}
const reset = () => {
  filterTask.value = undefined
  keyword.value = ''
  filterType.value = undefined
  filterConclusion.value = undefined
  filterStatus.value = undefined
  load()
}
const view = (record: any) => { current.value = record; detailOpen.value = true }

onMounted(async () => {
  load()
  try { tasks.value = await evalTaskApi.list() } catch (e) { /* 忽略 */ }
})
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.markdown { background: #fafafa; padding: 16px; border-radius: 6px; word-break: break-word; max-height: 70vh; overflow: auto; line-height: 1.7; font-size: 13px; }
.markdown :deep(pre) { background: #f0f0f0; padding: 10px; border-radius: 6px; overflow: auto; }
.markdown :deep(code) { font-size: 12px; }
.markdown :deep(table) { border-collapse: collapse; width: 100%; }
.markdown :deep(th), .markdown :deep(td) { border: 1px solid #e0e0e0; padding: 4px 8px; }
.markdown :deep(img) { max-width: 100%; }
</style>
