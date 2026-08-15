<template>
  <div class="mock-data-inserter">
    <a-dropdown :trigger="['click']" placement="bottomRight">
      <a-button size="small" type="dashed">
        <ThunderboltOutlined /> Mock
      </a-button>
      <template #overlay>
        <div class="mock-dropdown-panel">
          <div class="mock-search">
            <a-input
              v-model:value="searchKeyword"
              placeholder="搜索函数..."
              size="small"
              allow-clear
            >
              <template #prefix><SearchOutlined /></template>
            </a-input>
          </div>
          <div class="mock-function-list">
            <div
              v-for="func in filteredFunctions"
              :key="func.name"
              class="mock-function-item"
              @click="handleInsert(func)"
            >
              <div class="func-header">
                <span class="func-name">{{ func.name }}</span>
                <span class="func-syntax">{{ func.syntax }}</span>
              </div>
              <div class="func-desc">{{ func.description }}</div>
              <div class="func-example">示例: {{ func.example }}</div>
            </div>
            <div v-if="filteredFunctions.length === 0" class="mock-empty">
              未找到匹配的函数
            </div>
          </div>
        </div>
      </template>
    </a-dropdown>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ThunderboltOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { mockDataApi, type MockFunction } from '@/api/apiTest'

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'insert', text: string): void
}>()

const searchKeyword = ref('')
const functions = ref<MockFunction[]>([])

const filteredFunctions = computed(() => {
  if (!searchKeyword.value) return functions.value
  const kw = searchKeyword.value.toLowerCase()
  return functions.value.filter(
    f => f.name.toLowerCase().includes(kw) || f.description.includes(kw)
  )
})

async function loadFunctions() {
  try {
    const res = await mockDataApi.functions()
    functions.value = res.functions
  } catch (e) {
    console.error('加载Mock函数列表失败', e)
  }
}

function handleInsert(func: MockFunction) {
  const text = func.syntax
  // 如果有 modelValue，追加到末尾
  if (props.modelValue !== undefined) {
    emit('update:modelValue', props.modelValue + text)
  }
  emit('insert', text)
}

onMounted(() => {
  loadFunctions()
})
</script>

<style scoped>
.mock-data-inserter {
  display: inline-block;
}
.mock-dropdown-panel {
  width: 360px;
  max-height: 400px;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}
.mock-search {
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
}
.mock-function-list {
  max-height: 320px;
  overflow-y: auto;
}
.mock-function-item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #fafafa;
  transition: background 0.2s;
}
.mock-function-item:hover {
  background: #f5f5f5;
}
.func-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.func-name {
  font-weight: 600;
  color: #1890ff;
  font-size: 13px;
}
.func-syntax {
  font-family: monospace;
  font-size: 11px;
  color: #999;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
}
.func-desc {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}
.func-example {
  font-size: 11px;
  color: #999;
  font-family: monospace;
}
.mock-empty {
  padding: 30px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
</style>
