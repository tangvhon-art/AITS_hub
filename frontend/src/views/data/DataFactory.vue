<template>
  <div class="data-factory">
    <a-tabs :active-key="activeTab" @change="handleTabChange" class="factory-tabs">
      <a-tab-pane key="pools" tab="Mock 数据池">
        <router-view :key="route.fullPath" />
      </a-tab-pane>
      <a-tab-pane key="tools" tab="通用造数工具">
        <router-view />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

/** 依据当前路由路径决定激活 Tab：/tools → 通用造数工具，其余 → Mock 数据池 */
const activeTab = computed(() => (route.path.includes('/tools') ? 'tools' : 'pools'))

function handleTabChange(key: string) {
  const base = `/projects/${projectId}/data-factory`
  if (key === 'tools' && activeTab.value !== 'tools') {
    router.push(`${base}/tools`)
  } else if (key === 'pools' && activeTab.value !== 'pools') {
    router.push(`${base}/pools`)
  }
}
</script>

<style scoped>
.data-factory { padding: 0; }
.factory-tabs :deep(.ant-tabs-tab) { font-weight: 500; }
</style>
