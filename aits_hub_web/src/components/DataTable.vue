<template>
  <div class="data-table-wrapper">
    <a-table
      v-bind="pagination ? $attrs : {}"
      :columns="columns"
      :data-source="dataSource"
      :loading="loading"
      :pagination="pagination ? (paginationConfig as any) : false"
      :row-key="rowKey"
      :size="size"
      :row-selection="rowSelection"
      :scroll="scroll"
      @change="handleChange"
    >
      <template v-for="(_, name) in $slots" #[name]="slotData">
        <slot :name="name" v-bind="slotData" />
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TableProps } from 'ant-design-vue'

const props = withDefaults(defineProps<{
  columns?: any[]
  dataSource: any[]
  loading?: boolean
  rowKey?: string | ((record: any, index?: number) => any)
  size?: 'small' | 'middle' | 'large'
  page?: number
  pageSize?: number
  total?: number
  rowSelection?: Record<string, any>
  scroll?: Record<string, any>
  pagination?: boolean
}>(), {
  loading: false,
  rowKey: 'id',
  size: 'middle',
  rowSelection: undefined,
  scroll: undefined,
  pagination: true,
})

const emit = defineEmits<{
  change: [pag: { current: number; pageSize: number }]
}>()

/**
 * 受控模式：父组件传入 :page 时，由父组件管理分页状态（emit change 由父组件处理）。
 * 非受控模式：未传 :page 时，组件内部管理本地分页（翻页 + 每页条数切换自动生效）。
 */
const isControlled = computed(() => props.page !== undefined)

const innerPage = ref(1)
const innerPageSize = ref(10)

const current = computed(() => (isControlled.value ? props.page : innerPage.value))
const pageSize = computed(() => (isControlled.value ? props.pageSize : innerPageSize.value))
const total = computed(() =>
  isControlled.value ? props.total : (props.dataSource ? props.dataSource.length : 0),
)

const paginationConfig = computed(() => ({
  current: current.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
}))

function handleChange(pag: any) {
  if (isControlled.value) {
    emit('change', { current: pag.current, pageSize: pag.pageSize })
  } else {
    innerPage.value = pag.current
    innerPageSize.value = pag.pageSize
  }
}
</script>

<style scoped>
.data-table-wrapper {
  width: 100%;
}
</style>
