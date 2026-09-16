<template>
  <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }" layout="horizontal" size="middle">
    <a-form-item
      v-for="field in fields"
      :key="field.name"
      :label="field.label"
      :required="isRequired(field.name)"
      :extra="field.description || undefined"
    >
      <!-- 联动日期时间选择器 -->
      <a-date-picker
        v-if="fieldWidget(field)?.kind === 'datetime'"
        v-model:value="form[field.name]"
        show-time
        value-format="YYYY-MM-DD HH:mm:ss"
        :allow-clear="!isRequired(field.name)"
        style="width: 100%"
        :placeholder="fieldWidget(field)?.placeholder || '请选择日期时间'"
      />
      <!-- 日期选择器 -->
      <a-date-picker
        v-else-if="fieldWidget(field)?.kind === 'date'"
        v-model:value="form[field.name]"
        value-format="YYYY-MM-DD"
        :allow-clear="!isRequired(field.name)"
        style="width: 100%"
        :placeholder="fieldWidget(field)?.placeholder || '请选择日期'"
      />
      <!-- 联动文本输入 -->
      <a-input
        v-else-if="fieldWidget(field)?.kind === 'text'"
        v-model:value="form[field.name]"
        :allow-clear="!isRequired(field.name)"
        :placeholder="fieldWidget(field)?.placeholder || '请输入'"
      />
      <!-- 枚举 → 下拉 -->
      <a-select
        v-else-if="field.prop.enum"
        v-model:value="form[field.name]"
        :options="enumOptions(field.prop)"
        :allow-clear="!isRequired(field.name)"
        style="width: 100%"
        placeholder="请选择"
      />
      <!-- 布尔 → 开关 -->
      <a-switch
        v-else-if="field.prop.type === 'boolean'"
        v-model:checked="form[field.name]"
      />
      <!-- 数组 → 多选 -->
      <a-select
        v-else-if="field.prop.type === 'array'"
        v-model:value="form[field.name]"
        mode="multiple"
        :options="enumOptions(field.prop.items)"
        :allow-clear="!isRequired(field.name)"
        style="width: 100%"
        placeholder="请选择"
      />
      <!-- 整数 / 数字 -->
      <a-input-number
        v-else-if="field.prop.type === 'integer' || field.prop.type === 'number'"
        v-model:value="form[field.name]"
        :min="field.prop.minimum"
        :max="field.prop.maximum"
        :precision="field.prop.type === 'number' ? undefined : 0"
        style="width: 100%"
      />
      <!-- 多行文本 -->
      <a-textarea
        v-else-if="field.prop['x-multiline']"
        v-model:value="form[field.name]"
        :rows="4"
        placeholder="请输入内容"
        allow-clear
      />
      <!-- 普通文本 -->
      <a-input
        v-else
        v-model:value="form[field.name]"
        placeholder="请输入"
        allow-clear
      />
    </a-form-item>
  </a-form>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { ToolParamSchema } from '@/api/dataFactory'

const props = defineProps<{
  schema: ToolParamSchema
  /** 外部可注入的默认值（如重新生成随机 key） */
  defaults?: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, any>): void
  (e: 'change', value: Record<string, any>): void
}>()

/** 字段元信息 */
interface FieldMeta {
  name: string
  label: string
  description: string
  prop: any
}

const fields = computed<FieldMeta[]>(() => {
  const props_ = props.schema.properties || {}
  return Object.entries(props_).map(([name, prop]: [string, any]) => ({
    name,
    label: prop.title || name,
    description: prop.description || '',
    prop,
  }))
})

function defaultValue(prop: any): any {
  // 联动控件字段：默认不填（null），由输入类型决定渲染组件
  if (prop['x-widget-map']) return prop.default ?? null
  // 日期选择器：默认不填（null），由后端使用默认日期
  if (prop['x-widget'] === 'date' || prop['x-widget'] === 'datetime') return prop.default ?? null
  // 枚举优先：枚举字段默认取首项，避免落入枚举外值
  if (prop.enum) return prop.default ?? prop.enum[0]
  if (prop.type === 'integer' || prop.type === 'number') {
    // 有 minimum 时默认取最小合法值（如 size≥64、height≥5）
    return prop.default ?? (prop.minimum != null ? prop.minimum : 0)
  }
  if (prop.type === 'boolean') return prop.default ?? false
  if (prop.type === 'array') return prop.default ?? []
  return prop.default ?? ''
}

/** 解析字段渲染控件：x-widget 静态标记，或 x-widget-map 按依赖字段当前值动态切换 */
function fieldWidget(field: any): { kind: string; placeholder?: string } | null {
  const map = field.prop?.['x-widget-map']
  if (map) {
    const dep = map.depends || 'from_type'
    const cur = form[dep]
    const entry = map[cur] || map['*']
    if (entry) return { kind: entry.widget || 'text', placeholder: entry.placeholder }
  }
  const w = field.prop?.['x-widget']
  if (w === 'date' || w === 'datetime') return { kind: w }
  return null
}

/** 构建提交值：剔除 null/undefined（未填写的可选参数不提交，交给后端默认值） */
function buildPayload(): Record<string, any> {
  const payload: Record<string, any> = {}
  for (const [k, v] of Object.entries(form)) {
    if (v === null || v === undefined) continue
    payload[k] = v
  }
  return payload
}

const form = reactive<Record<string, any>>({})

/** 联动重置：依赖字段（如输入类型）切换时清空被联动字段值，避免新旧类型值混淆 */
const widgetMapFields = computed<any[]>(() => fields.value.filter((f: any) => f.prop?.['x-widget-map']))
watch(
  () => widgetMapFields.value.map((f: any) => form[f.prop['x-widget-map'].depends || 'from_type']),
  () => {
    for (const f of widgetMapFields.value) {
      form[f.name] = null
    }
  },
)

/** 初始化表单默认值（Schema 变化时重建） */
function resetForm() {
  for (const key of Object.keys(form)) {
    delete form[key]
  }
  for (const f of fields.value) {
    form[f.name] = props.defaults?.[f.name] ?? defaultValue(f.prop)
  }
  emitForm()
}

function isRequired(name: string): boolean {
  return (props.schema.required || []).includes(name)
}

/** 枚举选项：label 优先使用 x-enum-labels 中文标签，无则回退枚举原值 */
function enumOptions(prop: any): { value: any; label: string }[] {
  const values = prop?.enum || []
  const labels = prop?.['x-enum-labels'] || []
  return values.map((v: any, i: number) => ({
    value: v,
    label: labels[i] !== undefined ? String(labels[i]) : String(v),
  }))
}

function emitForm() {
  emit('update:modelValue', buildPayload())
  emit('change', buildPayload())
}

watch(() => props.schema, resetForm, { immediate: true, deep: true })
watch(() => props.defaults, () => {
  if (props.defaults) {
    for (const [k, v] of Object.entries(props.defaults)) {
      if (k in form) form[k] = v
    }
    emitForm()
  }
}, { deep: true })

/** 供父组件获取当前表单值 */
defineExpose({ getValue: () => buildPayload() })
</script>
