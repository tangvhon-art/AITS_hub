<template>
  <div class="search-bar">
    <slot />
    <div class="search-bar-actions">
      <a-space>
        <a-button type="primary" :loading="loading" @click="handleSearch">
          <template #icon><SearchOutlined /></template>
          {{ searchText }}
        </a-button>
        <a-button @click="handleReset">{{ resetText }}</a-button>
        <slot name="extra" />
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 通用搜索筛选栏组件
 *
 * 封装列表页的搜索筛选区域，统一搜索/重置按钮布局。
 * 筛选控件通过默认插槽插入，按钮通过事件通知父组件。
 *
 * 用法::
 *
 *   <SearchBar @search="loadData" @reset="handleReset">
 *     <a-form layout="inline">
 *       <a-form-item label="关键词">
 *         <a-input v-model:value="keyword" placeholder="搜索名称" />
 *       </a-form-item>
 *       <a-form-item label="状态">
 *         <a-select v-model:value="status" allow-clear>
 *           <a-select-option value="active">启用</a-select-option>
 *         </a-select>
 *       </a-form-item>
 *     </a-form>
 *   </SearchBar>
 */
import { SearchOutlined } from '@ant-design/icons-vue'

withDefaults(
  defineProps<{
    loading?: boolean
    searchText?: string
    resetText?: string
  }>(),
  {
    loading: false,
    searchText: '搜索',
    resetText: '重置',
  },
)

const emit = defineEmits<{
  search: []
  reset: []
}>()

function handleSearch() {
  emit('search')
}

function handleReset() {
  emit('reset')
}
</script>

<style scoped>
.search-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.search-bar-actions {
  flex-shrink: 0;
}
</style>
