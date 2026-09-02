<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card size="small"><a-statistic title="测评任务总数" :value="data.total_tasks || 0" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="已完成任务" :value="data.completed_tasks || 0" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="P0 高危问题" :value="data.p0_count || 0" :value-style="{ color: (data.p0_count || 0) > 0 ? '#cf1322' : '#3f8600' }" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="最近结论" :value="conclusionText(latestConclusion) || '-'" /></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="12">
        <a-card title="五维能力雷达（最近一次完整任务）" size="small">
          <div ref="radarRef" style="height: 320px"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="任务状态分布" size="small">
          <div ref="pieRef" style="height: 320px"></div>
        </a-card>
      </a-col>
    </a-row>

    <a-card title="最近测评任务" size="small" style="margin-top: 16px">
      <a-table :data-source="data.trend || []" :pagination="false" size="small" row-key="id">
        <a-table-column title="任务" data-index="name" />
        <a-table-column title="状态" data-index="status" width="120">
          <template #default="{ text }">
            <a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="结论" data-index="conclusion" width="110">
          <template #default="{ text }">
            <a-tag v-if="text" :color="conclusionColor(text)">{{ conclusionText(text) }}</a-tag>
            <span v-else>-</span>
          </template>
        </a-table-column>
        <a-table-column title="创建时间" data-index="created_at" width="180" />
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { evalDashboardApi } from '@/api/eval'

const data = ref<any>({})
const radarRef = ref<HTMLDivElement>()
const pieRef = ref<HTMLDivElement>()
let radarChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const latestConclusion = computed(() => {
  const trend = data.value.trend || []
  const latest = trend.find((t: any) => t.conclusion)
  return latest?.conclusion || ''
})

const statusText = (s: string) => ({ draft: '草稿', ready: '就绪', running: '执行中', completed: '已完成', failed: '失败', canceled: '已取消' } as any)[s] || s
const statusColor = (s: string) => ({ draft: 'default', ready: 'blue', running: 'processing', completed: 'success', failed: 'error', canceled: 'warning' } as any)[s] || 'default'
const conclusionText = (c: string) => ({ pass: '准入通过', conditional: '条件通过', reject: '准入驳回' } as any)[c] || c
const conclusionColor = (c: string) => ({ pass: 'green', conditional: 'orange', reject: 'red' } as any)[c] || 'default'

const renderCharts = () => {
  const radar = data.value.radar || {}
  const radarData = [radar.ai_judge || 0, radar.agent || 0, radar.business || 0, radar.redteam || 0, radar.manual || 0]
  radarChart = radarChart || (radarRef.value ? echarts.init(radarRef.value) : null)
  radarChart?.setOption({
    radar: {
      indicator: [
        { name: 'AI裁判', max: 5 }, { name: 'Agent交互', max: 5 },
        { name: '业务落地', max: 5 }, { name: '对抗红队', max: 5 }, { name: '人工', max: 5 },
      ],
    },
    series: [{ type: 'radar', data: [{ value: radarData, name: '综合能力' }] }],
    tooltip: {},
  })

  const statusCount = data.value.status_count || {}
  const pieData = Object.entries(statusCount).map(([k, v]) => ({ name: statusText(k), value: v as number }))
  pieChart = pieChart || (pieRef.value ? echarts.init(pieRef.value) : null)
  pieChart?.setOption({
    tooltip: { trigger: 'item' },
    series: [{ type: 'pie', radius: '62%', data: pieData }],
  })
}

const load = async () => {
  data.value = await evalDashboardApi.get()
  await nextTick()
  renderCharts()
}

onMounted(() => { load(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); radarChart?.dispose(); pieChart?.dispose() })
const resize = () => { radarChart?.resize(); pieChart?.resize() }
</script>
