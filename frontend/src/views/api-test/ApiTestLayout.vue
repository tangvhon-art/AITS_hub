<template>
  <div class="api-test-layout">
    <div class="api-test-sidebar">
      <div class="sidebar-header">
        <span class="title">接口测试</span>
      </div>
      <a-menu
        :selected-keys="[activeMenuKey]"
        @click="handleMenuClick"
      >
        <a-menu-item key="definitions">
          <template #icon><ApiOutlined /></template>
          接口管理
        </a-menu-item>
        <a-menu-item key="debug">
          <template #icon><ThunderboltOutlined /></template>
          接口调试
        </a-menu-item>
        <a-menu-item key="cases">
          <template #icon><CheckSquareOutlined /></template>
          测试用例
        </a-menu-item>
        <a-menu-item key="scenarios">
          <template #icon><AppstoreOutlined /></template>
          场景编排
        </a-menu-item>
        <a-menu-item key="executions">
          <template #icon><HistoryOutlined /></template>
          执行记录
        </a-menu-item>
        <a-menu-item key="mock">
          <template #icon><ExperimentOutlined /></template>
          Mock 服务
        </a-menu-item>
      </a-menu>
    </div>
    <div class="api-test-content">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
import {
  ApiOutlined, ThunderboltOutlined, CheckSquareOutlined,
  AppstoreOutlined, HistoryOutlined, ExperimentOutlined
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()

const activeMenuKey = computed(() => (route.meta.activeMenu as string) || 'definitions')

const handleMenuClick = ({ key }: { key: string }) => {
  const projectId = route.params.id
  router.push(`/projects/${projectId}/api-${key}`)
}
</script>

<style scoped>
.api-test-layout {
  display: flex;
  height: 100%;
  background: #fff;
}
.api-test-sidebar {
  width: 200px;
  border-right: 1px solid #f0f0f0;
  background: #fafafa;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}
.api-test-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
}
:deep(.ant-menu) {
  border-right: none;
  background: transparent;
}
</style>
