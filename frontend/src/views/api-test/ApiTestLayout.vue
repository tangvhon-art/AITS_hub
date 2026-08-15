<template>
  <div class="api-test-layout">
    <div class="api-test-sidebar" :class="{ collapsed: collapsed }">
      <div class="sidebar-header">
        <span v-if="!collapsed" class="title">接口测试</span>
        <span v-else class="title-collapsed">AT</span>
        <a-button type="text" size="small" class="collapse-btn" @click="collapsed = !collapsed">
          <template #icon>
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </template>
        </a-button>
      </div>
      <a-menu
        :selected-keys="[activeMenuKey]"
        :inline-collapsed="collapsed"
        @click="handleMenuClick"
      >
        <a-menu-item key="definitions">
          <template #icon><ApiOutlined /></template>
          <span>接口管理</span>
        </a-menu-item>
        <a-menu-item key="debug">
          <template #icon><ThunderboltOutlined /></template>
          <span>接口调试</span>
        </a-menu-item>
        <a-menu-item key="cases">
          <template #icon><CheckSquareOutlined /></template>
          <span>测试用例</span>
        </a-menu-item>
        <a-menu-item key="scenarios">
          <template #icon><AppstoreOutlined /></template>
          <span>场景编排</span>
        </a-menu-item>
        <a-menu-item key="executions">
          <template #icon><HistoryOutlined /></template>
          <span>执行记录</span>
        </a-menu-item>
        <a-menu-item key="mock">
          <template #icon><ExperimentOutlined /></template>
          <span>Mock 服务</span>
        </a-menu-item>
        <a-menu-item key="environments">
          <template #icon><EnvironmentOutlined /></template>
          <span>环境变量</span>
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
import { ref, computed } from 'vue'
import {
  ApiOutlined, ThunderboltOutlined, CheckSquareOutlined,
  AppstoreOutlined, HistoryOutlined, ExperimentOutlined,
  EnvironmentOutlined, MenuFoldOutlined, MenuUnfoldOutlined
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

const activeMenuKey = computed(() => (route.meta.activeMenu as string) || 'definitions')

const handleMenuClick = ({ key }: { key: string }) => {
  const projectId = route.params.id
  router.push(`/projects/${projectId}/api-test/${key}`)
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
  transition: width 0.2s;
  flex-shrink: 0;
}
.api-test-sidebar.collapsed {
  width: 64px;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sidebar-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}
.sidebar-header .title-collapsed {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
  width: 100%;
  text-align: center;
}
.collapse-btn {
  flex-shrink: 0;
}
.api-test-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
  min-width: 0;
}
:deep(.ant-menu) {
  border-right: none;
  background: transparent;
}
</style>
