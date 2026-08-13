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
