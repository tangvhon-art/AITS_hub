import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/projects',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/Projects.vue'),
        meta: { title: '项目管理', icon: 'Folder' }
      },
      {
        path: 'projects/:id/versions',
        name: 'Versions',
        component: () => import('@/views/Versions.vue'),
        meta: { title: '版本管理', icon: 'Tag' }
      },
      {
        path: 'projects/:id/requirements',
        name: 'Requirements',
        component: () => import('@/views/Requirements.vue'),
        meta: { title: '需求管理', icon: 'Document' }
      },
      {
        path: 'projects/:id/cases',
        name: 'Cases',
        component: () => import('@/views/Cases.vue'),
        meta: { title: '用例管理', icon: 'List' }
      },
      {
        path: 'projects/:id/execution',
        name: 'Execution',
        component: () => import('@/views/Execution.vue'),
        meta: { title: 'UI 自动化执行', icon: 'VideoPlay' }
      },
      {
        path: 'projects/:id/scripts',
        name: 'Scripts',
        component: () => import('@/views/Scripts.vue'),
        meta: { title: '自动化脚本库', icon: 'Code' }
      },
      {
        path: 'projects/:id/suites',
        name: 'AutomationSuites',
        component: () => import('@/views/AutomationSuites.vue'),
        meta: { title: '自动化编排', icon: 'Appstore' }
      },
      {
        path: 'projects/:id/suite-runs/:runId',
        name: 'SuiteRunDetail',
        component: () => import('@/views/SuiteRunDetail.vue'),
        meta: { title: '编排执行详情', icon: 'Appstore' }
      },
      {
        path: 'projects/:id/defects',
        name: 'Defects',
        component: () => import('@/views/Defects.vue'),
        meta: { title: '缺陷管理', icon: 'Bug' }
      },
      {
        path: 'projects/:id/reports',
        name: 'Reports',
        component: () => import('@/views/Reports.vue'),
        meta: { title: '测试报告', icon: 'FileText' }
      },
      {
        path: 'projects/:id/knowledge',
        name: 'Knowledge',
        component: () => import('@/views/Knowledge.vue'),
        meta: { title: '知识库', icon: 'Book' }
      },
      {
        path: 'projects/:id/plans',
        name: 'TestPlans',
        component: () => import('@/views/TestPlans.vue'),
        meta: { title: '测试计划', icon: 'Schedule' }
      },
      {
        path: 'projects/:id/dashboard',
        name: 'QualityDashboard',
        component: () => import('@/views/QualityDashboard.vue'),
        meta: { title: '质量看板', icon: 'Dashboard' }
      },
      {
        path: 'projects/:id/import-export',
        name: 'ImportExport',
        component: () => import('@/views/ImportExport.vue'),
        meta: { title: '数据导入导出', icon: 'Import' }
      },
      {
        path: 'agent-tasks',
        name: 'AgentTasks',
        component: () => import('@/views/AgentTasks.vue'),
        meta: { title: 'Agent 任务', icon: 'Robot' }
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/AuditLogs.vue'),
        meta: { title: '审计日志', icon: 'FileSearch' }
      },
      {
        path: 'llm-config',
        name: 'LLMConfig',
        component: () => import('@/views/LLMConfig.vue'),
        meta: { title: '模型配置', icon: 'Cpu' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.token) {
    next('/login')
  } else if (to.path === '/login' && userStore.token) {
    next('/')
  } else {
    next()
  }
})

export default router
