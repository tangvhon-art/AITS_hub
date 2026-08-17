<template>
  <a-drawer
    :open="visible"
    :title="title"
    :width="width"
    :body-style="{ paddingBottom: '40px' }"
    @close="handleClose"
  >
    <a-descriptions v-if="fields.length > 0" bordered :column="column" size="small">
      <a-descriptions-item
        v-for="field in fields"
        :key="field.key"
        :label="field.label"
        :span="field.span || 1"
      >
        <template v-if="field.render">
          <component :is="field.render(record[field.key], record)" />
        </template>
        <StatusTag v-else-if="field.statusType" :value="record[field.key]" />
        <span v-else>{{ formatValue(record[field.key]) }}</span>
      </a-descriptions-item>
    </a-descriptions>

    <slot name="extra" :record="record" />

    <template #footer>
      <div style="text-align: right">
        <a-button @click="handleClose">关闭</a-button>
        <slot name="footer" :record="record" />
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusTag from './StatusTag.vue'

export interface DetailField {
  key: string
  label: string
  span?: number
  statusType?: string
  render?: (value: any, record: any) => any
}

const props = withDefaults(defineProps<{
  visible: boolean
  title: string
  record?: Record<string, any>
  fields?: DetailField[]
  width?: number | string
  column?: number
}>(), {
  record: () => ({}),
  fields: () => [],
  width: 640,
  column: 2,
})

const emit = defineEmits<{
  (e: 'close'): void
}>()

const handleClose = () => emit('close')

const formatValue = (value: any): string => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
</script>
