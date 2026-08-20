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
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '智能助手', icon: 'RobotOutlined' }
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/Projects.vue'),
        meta: { title: '项目管理', icon: 'ProjectOutlined' }
      },
      {
        path: 'projects/:id/versions',
        name: 'Versions',
        component: () => import('@/views/Versions.vue'),
        meta: { title: '版本管理', icon: 'TagOutlined' }
      },
      {
        path: 'projects/:id/requirements',
        name: 'Requirements',
        component: () => import('@/views/Requirements.vue'),
        meta: { title: '需求管理', icon: 'FileTextOutlined' }
      },
      {
        path: 'projects/:id/cases',
        name: 'Cases',
        component: () => import('@/views/Cases.vue'),
        meta: { title: '用例管理', icon: 'UnorderedListOutlined' }
      },
      {
        path: 'projects/:id/case-reviews',
        name: 'CaseReviews',
        component: () => import('@/views/CaseReviews.vue'),
        meta: { title: '用例评审', icon: 'AuditOutlined' }
      },
      {
        path: 'prompts',
        name: 'Prompts',
        component: () => import('@/views/Prompts.vue'),
        meta: { title: 'Prompt 管理', icon: 'MessageOutlined' }
      },
      {
        path: 'projects/:id/execution',
        name: 'Execution',
        component: () => import('@/views/Execution.vue'),
        meta: { title: 'UI 自动化执行', icon: 'PlayCircleOutlined' }
      },
      {
        path: 'projects/:id/scripts',
        name: 'Scripts',
        component: () => import('@/views/Scripts.vue'),
        meta: { title: '自动化脚本库', icon: 'CodeOutlined' }
      },
      {
        path: 'projects/:id/suites',
        name: 'AutomationSuites',
        component: () => import('@/views/AutomationSuites.vue'),
        meta: { title: '自动化编排', icon: 'AppstoreOutlined' }
      },
      {
        path: 'projects/:id/ui-healing/records',
        name: 'UiHealingRecords',
        component: () => import('@/views/UiHealingRecords.vue'),
        meta: { title: '自愈记录', icon: 'MedicineBoxOutlined' }
      },
      {
        path: 'projects/:id/ui-healing/profiles',
        name: 'UiHealingProfiles',
        component: () => import('@/views/UiHealingProfiles.vue'),
        meta: { title: '页面知识', icon: 'ClusterOutlined' }
      },
      {
        path: 'projects/:id/suite-runs/:runId',
        name: 'SuiteRunDetail',
        component: () => import('@/views/SuiteRunDetail.vue'),
        meta: { title: '编排执行详情', hideInMenu: true }
      },
      {
        path: 'projects/:id/api-test',
        component: () => import('@/views/api-test/ApiTestLayout.vue'),
        meta: { title: '接口测试', icon: 'ApiOutlined' },
        children: [
          { path: '', redirect: { name: 'ApiDefinitions' } },
          { path: 'definitions', name: 'ApiDefinitions', component: () => import('@/views/api-test/ApiDefinitions.vue'), meta: { title: '接口管理', activeMenu: 'definitions' } },
          { path: 'definitions/:apiId', name: 'ApiDefinitionEdit', component: () => import('@/views/api-test/ApiDefinitionEdit.vue'), meta: { title: '接口编辑', activeMenu: 'definitions' } },
          { path: 'debug', name: 'ApiDebug', component: () => import('@/views/api-test/ApiDebug.vue'), meta: { title: '接口调试', activeMenu: 'debug' } },
          { path: 'cases', name: 'ApiCases', component: () => import('@/views/api-test/ApiCases.vue'), meta: { title: '测试用例', activeMenu: 'cases' } },
          { path: 'cases/:caseId', name: 'ApiCaseEdit', component: () => import('@/views/api-test/ApiCaseEdit.vue'), meta: { title: '用例编辑', activeMenu: 'cases' } },
          { path: 'scenarios', name: 'ApiScenarios', component: () => import('@/views/api-test/ApiScenarios.vue'), meta: { title: '场景编排', activeMenu: 'scenarios' } },
          { path: 'scenarios/:scenarioId', name: 'ApiScenarioEdit', component: () => import('@/views/api-test/ApiScenarioEdit.vue'), meta: { title: '场景编辑', activeMenu: 'scenarios' } },
          { path: 'executions', name: 'ApiExecutions', component: () => import('@/views/api-test/ApiExecutions.vue'), meta: { title: '执行记录', activeMenu: 'executions' } },
          { path: 'executions/:executionId', name: 'ApiExecutionDetail', component: () => import('@/views/api-test/ApiExecutionDetail.vue'), meta: { title: '执行详情', activeMenu: 'executions' } },
          { path: 'mock', name: 'ApiMock', component: () => import('@/views/api-test/ApiMock.vue'), meta: { title: 'Mock服务', activeMenu: 'mock' } },
          { path: 'environments', name: 'ApiEnvironments', component: () => import('@/views/api-test/ApiEnvironments.vue'), meta: { title: '环境变量', activeMenu: 'environments' } },
        ]
      },
      { path: 'projects/:id/definitions', redirect: to => `/projects/${to.params.id}/api-test/definitions` },
      { path: 'projects/:id/definitions/:apiId', redirect: to => `/projects/${to.params.id}/api-test/definitions/${to.params.apiId}` },
      { path: 'projects/:id/api-cases', redirect: to => `/projects/${to.params.id}/api-test/cases` },
      { path: 'projects/:id/api-cases/:caseId', redirect: to => `/projects/${to.params.id}/api-test/cases/${to.params.caseId}` },
      { path: 'projects/:id/api-debug', redirect: to => `/projects/${to.params.id}/api-test/debug` },
      { path: 'projects/:id/api-scenarios', redirect: to => `/projects/${to.params.id}/api-test/scenarios` },
      { path: 'projects/:id/api-scenarios/:scenarioId', redirect: to => `/projects/${to.params.id}/api-test/scenarios/${to.params.scenarioId}` },
      { path: 'projects/:id/api-executions', redirect: to => `/projects/${to.params.id}/api-test/executions` },
      { path: 'projects/:id/api-executions/:executionId', redirect: to => `/projects/${to.params.id}/api-test/executions/${to.params.executionId}` },
      { path: 'projects/:id/api-mock', redirect: to => `/projects/${to.params.id}/api-test/mock` },
      { path: 'projects/:id/api-environments', redirect: to => `/projects/${to.params.id}/api-test/environments` },
      {
        path: 'projects/:id/defects',
        name: 'Defects',
        component: () => import('@/views/Defects.vue'),
        meta: { title: '缺陷管理', icon: 'BugOutlined' }
      },
      {
        path: 'projects/:id/reports',
        name: 'Reports',
        component: () => import('@/views/Reports.vue'),
        meta: { title: '测试报告', icon: 'FileTextOutlined' }
      },
      {
        path: 'projects/:id/knowledge',
        name: 'Knowledge',
        component: () => import('@/views/Knowledge.vue'),
        meta: { title: '知识库', icon: 'BookOutlined' }
      },
      {
        path: 'projects/:id/plans',
        name: 'TestPlans',
        component: () => import('@/views/TestPlans.vue'),
        meta: { title: '测试计划', icon: 'ScheduleOutlined' }
      },
      {
        path: 'projects/:projectId/test-plans/:planId/edit',
        name: 'TestPlanEdit',
        component: () => import('@/views/TestPlanEdit.vue'),
        meta: { title: '测试计划编辑', hideInMenu: true }
      },
      {
        path: 'projects/:projectId/test-plans/:planId/run/:executionId',
        name: 'TestPlanRun',
        component: () => import('@/views/TestPlanRun.vue'),
        meta: { title: '执行进度', hideInMenu: true }
      },
      {
        path: 'projects/:projectId/test-plans/:planId/report/:executionId',
        name: 'TestPlanReport',
        component: () => import('@/views/TestPlanReport.vue'),
        meta: { title: '测试报告', hideInMenu: true }
      },
      {
        path: 'projects/:id/dashboard',
        name: 'QualityDashboard',
        component: () => import('@/views/QualityDashboard.vue'),
        meta: { title: '质量看板', icon: 'DashboardOutlined' }
      },
      {
        path: 'projects/:id/coverage',
        name: 'CoverageDashboard',
        component: () => import('@/views/coverage/CoverageDashboard.vue'),
        meta: { title: '覆盖率分析', icon: 'SafetyCertificateOutlined' }
      },
      {
        path: 'projects/:id/performance-tests',
        name: 'PerformanceTests',
        component: () => import('@/views/performance/PerformanceTests.vue'),
        meta: { title: '性能测试', icon: 'ThunderboltOutlined' }
      },
      {
        path: 'projects/:id/performance-tests/:testId',
        name: 'PerformanceTestEdit',
        component: () => import('@/views/performance/PerformanceTestEdit.vue'),
        meta: { title: '性能测试编辑', hideInMenu: true }
      },
      {
        path: 'projects/:id/performance-tests/:testId/runs',
        name: 'PerformanceTestRuns',
        component: () => import('@/views/performance/PerformanceTestRunDetail.vue'),
        meta: { title: '执行结果', hideInMenu: true }
      },
      {
        path: 'projects/:id/data-pools',
        name: 'DataPools',
        component: () => import('@/views/data/DataPools.vue'),
        meta: { title: '数据池', icon: 'DatabaseOutlined' }
      },
      {
        path: 'projects/:id/data-pools/:poolId',
        name: 'DataPoolEdit',
        component: () => import('@/views/data/DataPoolEdit.vue'),
        meta: { title: '数据池编辑', hideInMenu: true }
      },
      {
        path: 'projects/:id/import-export',
        name: 'ImportExport',
        component: () => import('@/views/ImportExport.vue'),
        meta: { title: '数据导入导出', icon: 'ImportOutlined', hideInMenu: true }
      },
      {
        path: 'agent-tasks',
        name: 'AgentTasks',
        component: () => import('@/views/AgentTasks.vue'),
        meta: { title: 'Agent 任务', icon: 'RobotOutlined' }
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/AuditLogs.vue'),
        meta: { title: '审计日志', icon: 'FileSearchOutlined' }
      },
      {
        path: 'llm-config',
        name: 'LLMConfig',
        component: () => import('@/views/LLMConfig.vue'),
        meta: { title: '模型配置', icon: 'SettingOutlined' }
      },
      {
        path: 'task-monitor',
        name: 'TaskMonitor',
        component: () => import('@/views/TaskMonitor.vue'),
        meta: { title: '任务监控', icon: 'MonitorOutlined' }
      },
      {
        path: 'notification/channels',
        name: 'NotificationChannels',
        component: () => import('@/views/notification/NotificationChannels.vue'),
        meta: { title: '通知渠道', icon: 'BellOutlined' }
      },
      {
        path: 'notification/rules',
        name: 'NotificationRules',
        component: () => import('@/views/notification/NotificationRules.vue'),
        meta: { title: '通知规则', icon: 'BellOutlined' }
      },
      {
        path: 'notification/records',
        name: 'NotificationRecords',
        component: () => import('@/views/notification/NotificationRecords.vue'),
        meta: { title: '通知记录', icon: 'BellOutlined' }
      },
      {
        path: 'mcp/connectors',
        name: 'MCPConnectors',
        component: () => import('@/views/MCPConnectors.vue'),
        meta: { title: 'MCP 连接器', icon: 'ApiOutlined' }
      },
      {
        path: 'skills',
        name: 'Skills',
        component: () => import('@/views/Skills.vue'),
        meta: { title: 'Skill 管理', icon: 'ThunderboltOutlined' }
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
