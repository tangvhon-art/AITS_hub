<template>
  <div class="eval-layout">
    <div class="eval-sidebar" :class="{ collapsed }">
      <div class="sidebar-header">
        <span v-if="!collapsed" class="title">AI 模型测评</span>
        <span v-else class="title-collapsed">EV</span>
        <a-button type="text" size="small" class="collapse-btn" @click="collapsed = !collapsed">
          <template #icon>
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </template>
        </a-button>
      </div>
      <a-menu :selected-keys="[activeMenuKey]" :inline-collapsed="collapsed" @click="handleMenuClick">
        <a-menu-item key="dashboard"><template #icon><DashboardOutlined /></template><span>测评总览</span></a-menu-item>
        <a-menu-item key="targets"><template #icon><RocketOutlined /></template><span>被测对象</span></a-menu-item>
        <a-menu-item key="datasets"><template #icon><DatabaseOutlined /></template><span>数据集与用例</span></a-menu-item>
        <a-menu-item key="tasks"><template #icon><PlayCircleOutlined /></template><span>测评任务</span></a-menu-item>
        <a-menu-item key="manual"><template #icon><SolutionOutlined /></template><span>人工校准</span></a-menu-item>
        <a-menu-item key="redteam"><template #icon><SafetyCertificateOutlined /></template><span>对抗红队</span></a-menu-item>
        <a-menu-item key="reports"><template #icon><FileTextOutlined /></template><span>测评报告</span></a-menu-item>
        <a-menu-item key="issues"><template #icon><BugOutlined /></template><span>问题台账</span></a-menu-item>
        <a-menu-item key="compare"><template #icon><SwapOutlined /></template><span>版本对比</span></a-menu-item>
      </a-menu>
    </div>
    <div class="eval-content">
      <router-view :key="route.fullPath" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DashboardOutlined, RocketOutlined, DatabaseOutlined, PlayCircleOutlined,
  SolutionOutlined, SafetyCertificateOutlined, FileTextOutlined, BugOutlined,
  SwapOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

const activeMenuKey = computed(() => (route.meta.activeMenu as string) || 'dashboard')

const handleMenuClick = ({ key }: { key: string }) => {
  router.push(`/eval/${key}`)
}
</script>

<style scoped>
.eval-layout {
  display: flex;
  height: 100%;
  background: #fff;
}
.eval-sidebar {
  width: 210px;
  border-right: 1px solid #f0f0f0;
  background: #fafafa;
  transition: width 0.2s;
  flex-shrink: 0;
  overflow-y: auto;
}
.eval-sidebar.collapsed {
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
  width: 100%;
  text-align: center;
}
.collapse-btn {
  flex-shrink: 0;
}
.eval-content {
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
