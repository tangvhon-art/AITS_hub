<template>
  <a-card :title="tool.title" :bordered="false" class="tool-panel">
    <template #extra>
      <span class="tool-name-pill">{{ tool.name }}</span>
    </template>

    <a-descriptions v-if="tool.description" :column="1" size="small" class="tool-desc">
      <a-descriptions-item>{{ tool.description }}</a-descriptions-item>
    </a-descriptions>

    <a-divider style="margin: 12px 0" />

    <!-- 参数区 -->
    <DataSchemaForm ref="formRef" :schema="tool.parameters" :defaults="extraDefaults" />

    <!-- 执行区 -->
    <div class="action-bar">
      <a-button type="primary" :loading="loading" @click="handleRun">
        <template #icon><PlayCircleOutlined /></template>
        {{ tool.is_generator ? '生成' : '执行' }}
      </a-button>
      <a-button :disabled="!result" @click="handleReset">清空结果</a-button>
      <a-space v-if="result && isGeneratorResult" class="result-actions">
        <a-button size="small" @click="handleCopy">复制</a-button>
        <a-button size="small" @click="handleExportCsv">导出 CSV</a-button>
        <a-button size="small" type="primary" ghost @click="handleImportPool">导入 Mock 数据池</a-button>
      </a-space>
    </div>

    <!-- 结果区 -->
    <ResultViewer v-if="result" :result="result" :tool-name="tool.name" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'
import { dataFactoryApi, type DataToolMeta, type ToolResult } from '@/api/dataFactory'
import DataSchemaForm from '@/components/DataSchemaForm.vue'
import ResultViewer from './ResultViewer.vue'

const props = defineProps<{
  tool: DataToolMeta
  projectId: number
}>()

const formRef = ref<InstanceType<typeof DataSchemaForm> | null>(null)
const form = ref<Record<string, any>>({})
const extraDefaults = ref<Record<string, any> | undefined>(undefined)
const result = ref<ToolResult | null>(null)
const loading = ref(false)

const isGeneratorResult = computed(() => props.tool.is_generator && Array.isArray(result.value?.result))

/** 参数 → 后端执行 */
async function handleRun() {
  const params = formRef.value?.getValue() ?? {}
  loading.value = true
  try {
    const res = await dataFactoryApi.runTool(props.tool.name, params)
    result.value = res.result
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}

function handleReset() {
  result.value = null
}

function handleCopy() {
  const text = typeof result.value === 'string' ? result.value : JSON.stringify(result.value, null, 2)
  navigator.clipboard?.writeText(text).then(() => message.success('已复制'))
}

function handleExportCsv() {
  const rows = result.value?.result
  if (!Array.isArray(rows) || rows.length === 0) return
  const headers = rows.every((r) => typeof r === 'object' && r !== null)
    ? Object.keys(rows[0])
    : ['value']
  const escape = (v: any) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [headers.join(','), ...rows.map((r) =>
    headers.map((h) => escape(typeof r === 'object' && r !== null ? r[h] : r)).join(','),
  )].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${props.tool.name}.csv`
  a.click()
  URL.revokeObjectURL(url)
  message.success('CSV 已导出')
}

/** 一键导入 Mock 数据池（生成 static 型） */
async function handleImportPool() {
  const rows = result.value?.result
  if (!Array.isArray(rows) || rows.length === 0) return
  // 字符串数组 → 包装为 {value} 对象数组
  const normalized = rows.map((r, i) => (typeof r === 'object' && r !== null ? r : { value: r, index: i + 1 }))
  try {
    await dataFactoryApi.importToPool(props.projectId, `${props.tool.title}${Date.now()}`, normalized)
    message.success(`已导入 Mock 数据池（${normalized.length} 行）`)
  } catch {
    // 拦截器已提示
  }
}
</script>

<style scoped>
.tool-panel { border-radius: 8px; }
.tool-name-pill {
  font-family: "SF Mono", Menlo, monospace; font-size: 12px;
  background: #eef2f7; color: #374151; border-radius: 4px; padding: 2px 8px;
}
.tool-desc :deep(.ant-descriptions-item-content) { color: #4b5563; }
.action-bar { display: flex; align-items: center; gap: 12px; margin: 8px 0 16px; }
.result-actions { margin-left: 8px; }
</style>
