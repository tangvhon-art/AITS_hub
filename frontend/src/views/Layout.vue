<template>
  <a-layout class="layout-container">
    <a-layout-sider v-model:collapsed="collapsed" :trigger="null" collapsible width="220" class="sider">
      <div class="logo">
        <BugOutlined :style="{ fontSize: '20px', color: '#1677ff' }" />
        <span v-if="!collapsed">AITS 平台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        v-model:openKeys="openKeys"
        mode="inline"
        @click="handleMenuClick"
        class="sider-menu"
      >
        <template v-for="item in globalMenus" :key="item.key">
          <a-sub-menu v-if="item.children && item.children.length" :key="item.key">
            <template #icon>
              <component :is="iconMap[item.icon || 'BellOutlined']" />
            </template>
            <template #title>{{ item.title }}</template>
            <a-menu-item v-for="child in item.children" :key="child.key">
              <span>{{ child.title }}</span>
            </a-menu-item>
          </a-sub-menu>
          <a-menu-item v-else :key="item.key">
            <template #icon>
              <component :is="iconMap[item.icon || 'RobotOutlined']" />
            </template>
            <span>{{ item.title }}</span>
          </a-menu-item>
        </template>
        <a-menu-divider v-if="projectMenus.length > 0" />
        <template v-for="item in projectMenus" :key="item.key">
          <a-sub-menu v-if="item.children && item.children.length" :key="item.key">
            <template #icon>
              <component :is="iconMap[item.icon || 'ProjectOutlined']" />
            </template>
            <template #title>{{ item.title }}</template>
            <a-menu-item v-for="child in item.children" :key="child.key">
              <span>{{ child.title }}</span>
            </a-menu-item>
          </a-sub-menu>
          <a-menu-item v-else :key="item.key">
            <template #icon>
              <component :is="iconMap[item.icon || 'FileTextOutlined']" />
            </template>
            <span>{{ item.title }}</span>
          </a-menu-item>
        </template>
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
import { useMenu } from '@/composables/useMenu'
import {
  BugOutlined,
  ProjectOutlined,
  FileTextOutlined,
  UnorderedListOutlined,
  PlayCircleOutlined,
  CodeOutlined,
  AppstoreOutlined,
  SettingOutlined,
  LogoutOutlined,
  CloseOutlined,
  ReloadOutlined,
  BookOutlined,
  RobotOutlined,
  ScheduleOutlined,
  DashboardOutlined,
  ImportOutlined,
  FileSearchOutlined,
  TagOutlined,
  MonitorOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
  MessageOutlined,
  AuditOutlined,
  BellOutlined
} from '@ant-design/icons-vue'
import HealingIcon from '@/components/icons/HealingIcon.vue'
import PageKnowledgeIcon from '@/components/icons/PageKnowledgeIcon.vue'

// 图标名 → 组件映射，供路由派生菜单动态渲染
const iconMap: Record<string, any> = {
  BugOutlined, ProjectOutlined, FileTextOutlined, UnorderedListOutlined,
  PlayCircleOutlined, CodeOutlined, AppstoreOutlined, SettingOutlined,
  BookOutlined, RobotOutlined, ScheduleOutlined, DashboardOutlined,
  ImportOutlined, FileSearchOutlined, TagOutlined, MonitorOutlined,
  ApiOutlined, ThunderboltOutlined, DatabaseOutlined, SafetyCertificateOutlined,
  MessageOutlined, AuditOutlined, BellOutlined,
  MedicineBoxOutlined: HealingIcon,
  ClusterOutlined: PageKnowledgeIcon,
}

interface TabItem {
  path: string
  title: string
  closable: boolean
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const currentProjectId = computed(() => route.params.id as string)
const currentProjectName = computed(() => {
  const projects = JSON.parse(localStorage.getItem('projects') || '[]')
  const p = projects.find((x: any) => x.id === Number(currentProjectId.value))
  return p?.name || ''
})

// 从路由派生菜单
const { globalMenus, projectMenus } = useMenu(() => currentProjectId.value)

const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])
const _initOpenKeys: string[] = []
if (route.path.startsWith('/notification/')) _initOpenKeys.push('/notification')
if (currentProjectId.value) _initOpenKeys.push('pm-group', 'ua-group', 'qa-group')
const openKeys = ref<string[]>(_initOpenKeys)
const openTabs = ref<TabItem[]>([])

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
  if (!openTabs.value.find(t => t.path === '/dashboard')) {
    openTabs.value.unshift({ path: '/dashboard', title: '智能助手', closable: false })
  }
}

// 检测是否为浏览器刷新，若是则只保留当前标签
function handleRefreshReset() {
  const nav = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
  const isReload = nav.length > 0 && nav[0].type === 'reload'
  if (isReload) {
    const currentPath = route.path
    const currentTitle = getPageTitle()
    const kept: TabItem[] = [{ path: '/dashboard', title: '智能助手', closable: false }]
    if (currentPath !== '/dashboard' && currentPath !== '/projects') {
      kept.push({ path: currentPath, title: currentTitle, closable: true })
    }
    openTabs.value = kept
    saveTabs()
    return true
  }
  return false
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
      closable: path !== '/dashboard' && path !== '/projects'
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

watch(currentProjectId, (newId) => {
  if (newId) {
    const groups = ['pm-group', 'ua-group', 'qa-group']
    const current = openKeys.value
    for (const g of groups) {
      if (!current.includes(g)) current.push(g)
    }
  }
})

onMounted(() => {
  const wasRefresh = handleRefreshReset()
  if (!wasRefresh) {
    loadTabs()
  }
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
  overflow: hidden;
}

.sider {
  background: #fff;
  border-right: 1px solid #f0f0f0;
  box-shadow: 2px 0 8px 0 rgba(29, 35, 41, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 64px;
  flex-shrink: 0;
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
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

/* 自定义滚动条样式 */
.sider-menu::-webkit-scrollbar {
  width: 4px;
}

.sider-menu::-webkit-scrollbar-track {
  background: transparent;
}

.sider-menu::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 2px;
}

.sider-menu::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
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
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
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
  flex: 1;
  min-height: 0;
}

/* 内容区滚动条 - 缩小宽度，降低对 tabs 的遮挡 */
.main-content::-webkit-scrollbar {
  width: 5px;
}

.main-content::-webkit-scrollbar-track {
  background: transparent;
}

.main-content::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 3px;
}

.main-content::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

:deep(.ant-layout-sider) {
  background: #fff;
  overflow: hidden;
}

:deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
  height: 100%;
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
