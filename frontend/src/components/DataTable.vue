<template>
  <div class="data-table-wrapper">
    <a-table
      :columns="columns"
      :data-source="dataSource"
      :loading="loading"
      :pagination="paginationConfig"
      :row-key="rowKey"
      :size="size"
      @change="handleChange"
    >
      <template v-for="(_, name) in $slots" #[name]="slotData">
        <slot :name="name" v-bind="slotData" />
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TableProps } from 'ant-design-vue'

const props = withDefaults(defineProps<{
  columns: any[]
  dataSource: any[]
  loading?: boolean
  rowKey?: string | ((record: any) => any)
  size?: 'small' | 'middle' | 'large'
  page?: number
  pageSize?: number
  total?: number
}>(), {
  loading: false,
  rowKey: 'id',
  size: 'middle',
  page: 1,
  pageSize: 20,
  total: 0,
})

const emit = defineEmits<{
  change: [page: number, pageSize: number]
}>()

const paginationConfig = computed(() => ({
  current: props.page,
  pageSize: props.pageSize,
  total: props.total,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
}))

function handleChange(pag: any) {
  emit('change', pag.current, pag.pageSize)
}
</script>

<style scoped>
.data-table-wrapper {
  width: 100%;
}
</style>
