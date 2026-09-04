<template>
  <div class="result-viewer">
    <!-- 图片类：二维码 / 条形码 / Base64 转图 -->
    <template v-if="imageUrl">
      <a-image :src="imageUrl" :width="Math.min(280, imageWidth)" class="result-image" />
      <div class="image-actions">
        <a-button size="small" type="link" @click="downloadImage">下载图片</a-button>
      </div>
    </template>

    <!-- Diff 类：json_compare / text_compare -->
    <template v-else-if="diffItems">
      <a-table
        :data-source="diffItems"
        :columns="diffColumns"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        size="small"
        row-key="__idx"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'op'">
            <a-tag :color="opColor(record.op)">{{ opText(record.op) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'old' || column.key === 'new'">
            <span class="diff-cell">{{ displayValue(column.key === 'old' ? record.old : record.new) }}</span>
          </template>
        </template>
      </a-table>
    </template>

    <!-- 生成类数组 → 表格 -->
    <template v-else-if="Array.isArray(result?.result)">
      <a-table
        :data-source="tableRows"
        :columns="tableColumns"
        :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }"
        size="small"
        row-key="__idx"
        :scroll="{ x: 'max-content' }"
      />
    </template>

    <!-- 文本 / 对象 → 代码块 -->
    <template v-else>
      <pre class="result-code">{{ prettyText }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { message } from 'ant-design-vue'
import type { ToolResult } from '@/api/dataFactory'

const props = defineProps<{
  result: ToolResult
  toolName: string
}>()

/** 图片 data URL（二维码/条形码/Base64转图） */
const imageUrl = computed(() => {
  const r: any = props.result
  if (typeof r === 'string' && r.startsWith('data:image')) return r
  if (typeof r?.data_url === 'string' && r.data_url.startsWith('data:image')) return r.data_url
  return ''
})

const imageWidth = computed(() => {
  const r: any = props.result
  return typeof r?.size === 'number' ? Math.min(r.size, 280) : 280
})

function downloadImage() {
  const url = imageUrl.value
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = `${props.toolName}.png`
  a.click()
  message.success('图片已下载')
}

/** Diff 结果：json_compare 的 diff 数组 / text_compare 的 diff_lines 数组 */
const diffItems = computed<any[] | null>(() => {
  const r = props.result
  if (r && Array.isArray(r.diff)) {
    return r.diff.map((d: any, i: number) => ({ ...d, __idx: i }))
  }
  if (r && Array.isArray(r.diff_lines)) {
    return r.diff_lines.map((d: any, i: number) => ({ ...d, __idx: i }))
  }
  return null
})

const diffColumns = [
  { title: '类型', key: 'op', width: 90 },
  { title: '路径/行号', dataIndex: 'path', key: 'path', width: 140,
    customRender: ({ record }: any) => record.path ?? (record.line_no != null ? `L${record.line_no}` : '-') },
  { title: '旧值', key: 'old', ellipsis: true },
  { title: '新值', key: 'new', ellipsis: true },
]

const opColor = (op: string) => ({ added: 'green', removed: 'red', changed: 'orange' })[op] || 'default'
const opText = (op: string) => ({ added: '新增', removed: '删除', changed: '修改' })[op] || op

function displayValue(v: any): string {
  if (v === null || v === undefined) return '-'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** 判断是否为可渲染的颜色值（HEX / RGB / HSL） */
function isColorLike(v: string): boolean {
  return /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v)
    || /^rgb\(/.test(v)
    || /^hsl\(/.test(v)
}

/** 生成类数组 → 表格数据 */
const tableRows = computed<any[]>(() => {
  const rows = props.result?.result
  if (!Array.isArray(rows)) return []
  return rows.map((r, i) => (typeof r === 'object' && r !== null ? { ...r, __idx: i } : { value: r, __idx: i }))
})

const tableColumns = computed<any[]>(() => {
  const rows = props.result?.result
  if (!Array.isArray(rows) || rows.length === 0) return []
  const sample = rows.find((r) => typeof r === 'object' && r !== null)
  const keys = sample ? Object.keys(sample) : ['value']
  return keys.map((k) => ({
    title: k === 'value' ? '生成结果' : k,
    dataIndex: k,
    key: k,
    ellipsis: true,
    width: k === '__idx' ? 60 : undefined,
    customRender: ({ record }: any) => {
      const v = record[k]
      if (typeof v === 'object' && v !== null) return JSON.stringify(v)
      const s = String(v)
      if (isColorLike(s)) {
        return h('span', { class: 'color-cell' }, [
          h('span', { class: 'color-swatch', style: { background: s } }),
          s,
        ])
      }
      return v
    },
  }))
})

/** 文本 / 对象展示 */
const prettyText = computed(() => {
  const r = props.result
  if (typeof r === 'string') return r
  if (r && typeof r.result === 'string') return r.result
  return JSON.stringify(r, null, 2)
})
</script>

<style scoped>
.result-viewer { margin-top: 8px; }
.result-image { border: 1px solid #f0f0f0; border-radius: 8px; background: #fff; padding: 8px; }
.image-actions { margin-top: 4px; }
.diff-cell { font-family: "SF Mono", Menlo, monospace; font-size: 12.5px; white-space: pre-wrap; word-break: break-all; }
.color-cell { display: inline-flex; align-items: center; gap: 6px; font-family: "SF Mono", Menlo, monospace; font-size: 12.5px; }
.color-swatch {
  display: inline-block; width: 14px; height: 14px; border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.15); flex-shrink: 0;
}
.result-code {
  background: #0f1e33; color: #d5e0ee; padding: 14px 16px; border-radius: 8px;
  overflow-x: auto; font-size: 12.5px; line-height: 1.6; max-height: 420px; overflow-y: auto;
}
</style>
