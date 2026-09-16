<template>
  <div v-if="html" class="md-view" v-html="html"></div>
  <div v-else class="md-view-empty">{{ emptyText }}</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = withDefaults(
  defineProps<{
    /** Markdown 原文 */
    content?: string
    /** 空内容占位文案 */
    emptyText?: string
  }>(),
  { content: '', emptyText: '暂无内容' },
)

/** 轻量 XSS 清洗：移除脚本/危险标签与事件属性（不引入额外依赖） */
function sanitizeHtml(raw: string): string {
  const doc = new DOMParser().parseFromString(raw, 'text/html')
  doc.querySelectorAll('script, iframe, object, embed, link, meta, style, form').forEach((el) => el.remove())
  doc.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase()
      if (name.startsWith('on')) el.removeAttribute(attr.name)
      if ((name === 'href' || name === 'src') && attr.value.trim().toLowerCase().startsWith('javascript:')) {
        el.removeAttribute(attr.name)
      }
    }
  })
  return doc.body.innerHTML
}

const html = computed(() => {
  if (!props.content) return ''
  try {
    return sanitizeHtml(marked.parse(props.content, { async: false }) as string)
  } catch {
    return sanitizeHtml((props.content || '').replace(/\n/g, '<br>'))
  }
})
</script>

<style scoped>
.md-view {
  line-height: 1.7;
  font-size: 13.5px;
  word-break: break-word;
}
.md-view :deep(h1),
.md-view :deep(h2),
.md-view :deep(h3) {
  margin: 14px 0 8px;
  font-weight: 600;
  line-height: 1.4;
}
.md-view :deep(p) { margin: 6px 0; }
.md-view :deep(ul),
.md-view :deep(ol) { padding-left: 22px; margin: 6px 0; }
.md-view :deep(pre) {
  background: #f6f8fa;
  color: #24292f;
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.md-view :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 12.5px;
  font-family: 'SF Mono', 'Menlo', Consolas, monospace;
}
.md-view :deep(pre code) {
  background: none;
  color: #24292f;
  padding: 0;
}
.md-view :deep(a) { color: #1d6fa5; }
.md-view :deep(table) { border-collapse: collapse; margin: 8px 0; }
.md-view :deep(th),
.md-view :deep(td) { border: 1px solid #e4e3dd; padding: 6px 10px; }
.md-view :deep(blockquote) {
  border-left: 3px solid #d9d9d9;
  margin: 8px 0;
  padding-left: 12px;
  color: #6b7280;
}
.md-view :deep(hr) { border: none; border-top: 1px solid #e4e3dd; margin: 12px 0; }
.md-view-empty {
  color: #999;
  padding: 12px 0;
  font-size: 13px;
}
</style>
