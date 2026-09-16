<template>
  <a-modal
    v-model:open="visible"
    :title="title"
    :width="640"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <div class="batch-edit">
      <div class="mode-bar">
        <a-radio-group v-model:value="mode" button-style="solid" size="small">
          <a-radio-button value="comma">逗号模式</a-radio-button>
          <a-radio-button value="colon">冒号模式</a-radio-button>
        </a-radio-group>
        <span class="format-hint">{{ formatHint }}</span>
      </div>
      <a-textarea
        v-model:value="rawText"
        :rows="12"
        :placeholder="placeholderText"
        class="batch-textarea"
      />
      <div class="help-text">
        数据格式遵循《标准 CSV 规范》字段之间以英文逗号(,)分隔，多条记录以换行分隔
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface KVItem {
  key: string
  value: string
  description?: string
  enabled: boolean
}

const props = withDefaults(defineProps<{
  open: boolean
  title?: string
  showDescription?: boolean
}>(), {
  title: '批量编辑',
  showDescription: false,
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'confirm', data: KVItem[]): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const mode = ref<'comma' | 'colon'>('comma')
const rawText = ref('')

const fields = computed(() => {
  if (props.showDescription) {
    return ['启用', '参数名', '参数值', '描述']
  }
  return ['启用', '参数名', '参数值']
})

const formatHint = computed(() => {
  if (mode.value === 'comma') {
    return `格式: ${fields.value.join(',')}`
  }
  return '格式: 参数名:参数值 (每行一条，可选前缀 # 禁用)'
})

const placeholderText = computed(() => {
  if (mode.value === 'comma') {
    if (props.showDescription) {
      return `true,Content-Type,application/json,内容类型\nfalse,Authorization,,认证头`
    }
    return `true,Content-Type,application/json\nfalse,Authorization,Bearer xxx`
  }
  return `Content-Type: application/json\n# Authorization: Bearer xxx`
})

watch(() => props.open, (val) => {
  if (val) {
    rawText.value = ''
    mode.value = 'comma'
  }
})

function parseComma(text: string): KVItem[] {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l)
  return lines.map(line => {
    const parts = parseCSVLine(line)
    const enabled = parts[0]?.toLowerCase() !== 'false' && parts[0] !== '0'
    const key = parts[1] || ''
    const value = parts[2] || ''
    if (props.showDescription) {
      return { key, value, description: parts[3] || '', enabled }
    }
    return { key, value, enabled }
  })
}

function parseCSVLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"' && line[i - 1] !== '\\') {
      inQuotes = !inQuotes
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  result.push(current.trim())
  return result
}

function parseColon(text: string): KVItem[] {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l)
  return lines.map(line => {
    let enabled = true
    if (line.startsWith('#')) {
      enabled = false
      line = line.slice(1).trim()
    }
    const colonIdx = line.indexOf(':')
    if (colonIdx === -1) {
      return { key: line, value: '', enabled }
    }
    const key = line.slice(0, colonIdx).trim()
    const value = line.slice(colonIdx + 1).trim()
    if (props.showDescription) {
      return { key, value, description: '', enabled }
    }
    return { key, value, enabled }
  })
}

function handleOk() {
  const text = rawText.value.trim()
  if (!text) {
    visible.value = false
    return
  }
  const parsed = mode.value === 'comma' ? parseComma(text) : parseColon(text)
  emit('confirm', parsed)
  visible.value = false
}

function handleCancel() {
  visible.value = false
}
</script>

<style scoped>
.batch-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mode-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.format-hint {
  color: #8c8c8c;
  font-size: 13px;
}
.batch-textarea {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}
.help-text {
  color: #8c8c8c;
  font-size: 12px;
}
</style>
