<template>
  <a-layout class="layout-container">
    <a-layout-sider v-model:collapsed="collapsed" :trigger="null" collapsible width="220" class="sider">
      <div class="logo">
        <BugOutlined :style="{ fontSize: '20px', color: '#1677ff' }" />
        <span v-if="!collapsed">AITS 平台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        mode="inline"
        @click="handleMenuClick"
        class="sider-menu"
      >
        <a-menu-item key="/projects">
          <template #icon>
            <ProjectOutlined />
          </template>
          <span>项目管理</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/requirements`">
          <template #icon>
            <FileTextOutlined />
          </template>
          <span>需求管理</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/cases`">
          <template #icon>
            <UnorderedListOutlined />
          </template>
          <span>用例管理</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/execution`">
          <template #icon>
            <PlayCircleOutlined />
          </template>
          <span>UI 自动化</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/defects`">
          <template #icon>
            <BugOutlined />
          </template>
          <span>缺陷管理</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/reports`">
          <template #icon>
            <FileTextOutlined />
          </template>
          <span>测试报告</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/knowledge`">
          <template #icon>
            <BookOutlined />
          </template>
          <span>知识库</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/plans`">
          <template #icon>
            <ScheduleOutlined />
          </template>
          <span>测试计划</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/dashboard`">
          <template #icon>
            <DashboardOutlined />
          </template>
          <span>质量看板</span>
        </a-menu-item>
        <a-menu-item v-if="currentProjectId" :key="`/projects/${currentProjectId}/import-export`">
          <template #icon>
            <ImportOutlined />
          </template>
          <span>数据导入导出</span>
        </a-menu-item>
        <a-menu-item key="/agent-tasks">
          <template #icon>
            <RobotOutlined />
          </template>
          <span>Agent 任务</span>
        </a-menu-item>
        <a-menu-item key="/audit-logs">
          <template #icon>
            <FileSearchOutlined />
          </template>
          <span>审计日志</span>
        </a-menu-item>
        <a-menu-item key="/llm-config">
          <template #icon>
            <SettingOutlined />
          </template>
          <span>模型配置</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="header">
        <div class="header-left">
          <span class="page-title">{{ route.meta.title || 'AITS 智能测试管理平台' }}</span>
        </div>
        <div class="header-right">
          <a-dropdown>
            <span class="user-info">
              <a-avatar size="small" style="background-color: #1677ff; margin-right: 8px">
                {{ (userStore.userInfo?.username || 'U').charAt(0).toUpperCase() }}
              </a-avatar>
              {{ userStore.userInfo?.username || '用户' }}
            </span>
            <template #overlay>
              <a-menu @click="handleCommand">
                <a-menu-item key="logout">
                  <LogoutOutlined />
                  退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 多标签页导航栏 -->
      <div class="tabs-bar">
        <div class="tabs-scroll">
          <div
            v-for="tab in openTabs"
            :key="tab.path"
            class="tab-item"
            :class="{ active: tab.path === route.path }"
            @click="switchTab(tab)"
          >
            <ReloadOutlined v-if="tab.path === route.path" class="tab-reload" @click.stop="refreshTab" />
            <span class="tab-title">{{ tab.title }}</span>
            <CloseOutlined
              v-if="tab.closable"
              class="tab-close"
              @click.stop="closeTab(tab)"
            />
          </div>
        </div>
      </div>

      <a-layout-content class="main-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  BugOutlined,
  ProjectOutlined,
  FileTextOutlined,
  UnorderedListOutlined,
  PlayCircleOutlined,
  SettingOutlined,
  LogoutOutlined,
  CloseOutlined,
  ReloadOutlined,
  BookOutlined,
  RobotOutlined,
  ScheduleOutlined,
  DashboardOutlined,
  ImportOutlined,
  FileSearchOutlined
} from '@ant-design/icons-vue'

interface TabItem {
  path: string
  title: string
  closable: boolean
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])
const openTabs = ref<TabItem[]>([])

const currentProjectId = computed(() => route.params.id as string)
const currentProjectName = computed(() => {
  const projects = JSON.parse(localStorage.getItem('projects') || '[]')
  const p = projects.find((x: any) => x.id === Number(currentProjectId.value))
  return p?.name || ''
})

// 从 localStorage 恢复标签页
function loadTabs() {
  const saved = localStorage.getItem('open_tabs')
  if (saved) {
    try {
      openTabs.value = JSON.parse(saved)
    } catch {
      openTabs.value = []
    }
  }
  // 确保首页标签存在
  if (!openTabs.value.find(t => t.path === '/projects')) {
    openTabs.value.unshift({ path: '/projects', title: '项目管理', closable: false })
  }
}

// 保存标签页到 localStorage
function saveTabs() {
  localStorage.setItem('open_tabs', JSON.stringify(openTabs.value))
}

// 获取页面标题
function getPageTitle(): string {
  if (route.meta.title) return route.meta.title as string
  const id = route.params.id
  if (id && currentProjectName.value) {
    return `${currentProjectName.value} - ${route.meta.title || ''}`
  }
  return '页面'
}

// 添加标签页
function addTab() {
  const path = route.path
  const title = getPageTitle()
  const existing = openTabs.value.find(t => t.path === path)
  if (!existing) {
    openTabs.value.push({
      path,
      title,
      closable: path !== '/projects'
    })
    saveTabs()
  } else if (existing.title !== title) {
    existing.title = title
    saveTabs()
  }
}

// 切换标签页
function switchTab(tab: TabItem) {
  if (tab.path !== route.path) {
    router.push(tab.path)
  }
}

// 关闭标签页
function closeTab(tab: TabItem) {
  const index = openTabs.value.findIndex(t => t.path === tab.path)
  if (index === -1) return

  openTabs.value.splice(index, 1)
  saveTabs()

  // 如果关闭的是当前标签页，跳转到相邻标签页
  if (tab.path === route.path) {
    const nextTab = openTabs.value[index] || openTabs.value[index - 1] || openTabs.value[0]
    if (nextTab) {
      router.push(nextTab.path)
    }
  }
}

// 刷新当前标签页
function refreshTab() {
  window.location.reload()
}

watch(
  () => route.path,
  (path) => {
    selectedKeys.value = [path]
    addTab()
  }
)

onMounted(() => {
  loadTabs()
  addTab()
  if (!userStore.userInfo) {
    userStore.fetchUserInfo()
  }
})

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}

function handleCommand({ key }: { key: string }) {
  if (key === 'logout') {
    userStore.logout()
    localStorage.removeItem('open_tabs')
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sider {
  background: #fff;
  border-right: 1px solid #f0f0f0;
  box-shadow: 2px 0 8px 0 rgba(29, 35, 41, 0.05);
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(0, 0, 0, 0.88);
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #f0f0f0;
}

.sider-menu {
  border-right: none;
}

.header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f0f0f0;
  height: 56px;
  line-height: 56px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: rgba(0, 0, 0, 0.88);
  font-size: 14px;
}

/* 多标签页导航栏 */
.tabs-bar {
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  padding: 6px 12px 0;
  overflow: hidden;
}

.tabs-scroll {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tabs-scroll::-webkit-scrollbar {
  display: none;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  flex-shrink: 0;
  position: relative;
  margin-bottom: -1px;
}

.tab-item:hover {
  color: #1677ff;
}

.tab-item.active {
  color: #1677ff;
  background: #fff;
  border-bottom-color: #fff;
  font-weight: 500;
}

.tab-item.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #1677ff;
}

.tab-reload {
  font-size: 12px;
  cursor: pointer;
  transition: transform 0.3s;
}

.tab-reload:hover {
  transform: rotate(180deg);
}

.tab-close {
  font-size: 10px;
  color: rgba(0, 0, 0, 0.45);
  cursor: pointer;
  border-radius: 2px;
  padding: 2px;
  transition: all 0.2s;
}

.tab-close:hover {
  color: #fff;
  background: #ff4d4f;
}

.main-content {
  background: #fafafa;
  overflow-y: auto;
}

:deep(.ant-layout-sider) {
  background: #fff;
}

:deep(.ant-menu-light .ant-menu-item-selected) {
  background-color: #e6f4ff;
  color: #1677ff;
}

:deep(.ant-menu-light .ant-menu-item-selected .anticon) {
  color: #1677ff;
}

:deep(.ant-menu-inline .ant-menu-item) {
  margin: 4px 8px;
  width: calc(100% - 16px);
  border-radius: 6px;
}
</style>
