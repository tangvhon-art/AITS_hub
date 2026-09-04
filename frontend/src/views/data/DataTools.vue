<template>
  <div class="data-tools">
    <div class="tools-layout">
      <!-- 左侧：六类工具导航 -->
      <aside class="tools-sidebar">
        <div
          v-for="cat in categories"
          :key="cat.key"
          class="cat-block"
        >
          <div class="cat-title">
            <component :is="iconMap[cat.icon] || FileTextOutlined" />
            <span>{{ cat.title }}</span>
          </div>
          <a-menu
            :selected-keys="[currentTool]"
            mode="inline"
            :style="{ borderInlineEnd: 'none' }"
            @click="handleSelectTool"
          >
            <a-menu-item v-for="tool in cat.tools" :key="tool.name">
              <span class="tool-name">{{ tool.title }}</span>
            </a-menu-item>
          </a-menu>
        </div>
      </aside>

      <!-- 右侧：工具面板 -->
      <section class="tools-workspace">
        <ToolPanel
          v-if="currentToolMeta"
          :key="currentToolMeta.name"
          :tool="currentToolMeta"
          :project-id="projectId"
        />
        <a-empty v-else description="请从左侧选择工具" style="margin-top: 120px" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  FileTextOutlined,
  ExperimentOutlined,
  QrcodeOutlined,
  ToolOutlined,
  LockOutlined,
  FontSizeOutlined,
} from '@ant-design/icons-vue'
import { dataFactoryApi, type DataToolCategory, type DataToolMeta } from '@/api/dataFactory'
import ToolPanel from './ToolPanel.vue'

const route = useRoute()
const projectId = Number(route.params.id)

const categories = ref<DataToolCategory[]>([])
const loading = ref(false)
const currentTool = ref('')

/** 图标映射（与后端 CATEGORY_META.icon 对应） */
const iconMap: Record<string, any> = {
  ExperimentOutlined,
  FileTextOutlined,
  FontSizeOutlined,
  QrcodeOutlined,
  ToolOutlined,
  LockOutlined,
}

const currentToolMeta = computed<DataToolMeta | null>(() => {
  for (const cat of categories.value) {
    const found = cat.tools.find((t) => t.name === currentTool.value)
    if (found) return found
  }
  return null
})

function handleSelectTool({ key }: { key: string }) {
  currentTool.value = key
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await dataFactoryApi.getCategories()
    categories.value = res.categories
    // 默认选中第一个工具
    const first = res.categories.find((c) => c.tools.length > 0)
    if (first?.tools?.length) {
      currentTool.value = first.tools[0].name
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.data-tools { padding: 0; }
.tools-layout { display: flex; gap: 16px; align-items: flex-start; }
.tools-sidebar {
  width: 230px; flex-shrink: 0; background: #fff; border: 1px solid #f0f0f0;
  border-radius: 8px; padding: 8px; max-height: calc(100vh - 200px); overflow-y: auto;
}
.cat-block { margin-bottom: 4px; }
.cat-title {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px 2px;
  font-size: 13px; font-weight: 600; color: #1f2937;
}
.tools-workspace { flex: 1; min-width: 0; }
.tool-name { font-size: 13px; }
</style>
