/**
 * 菜单派生工具
 *
 * 从 router.options.routes 派生侧边栏菜单，消除 Layout.vue 中硬编码的菜单项。
 *
 * 路由 meta 约定：
 * - title: string         菜单标题（必填，否则不出现在菜单中）
 * - icon: string          图标组件名（PascalCase，如 'RobotOutlined'）
 * - hideInMenu: boolean   设为 true 则不在菜单中显示（详情页/编辑页）
 * - projectScoped: boolean  自动推断：路径含 ':id' 或 ':projectId' 时为项目级菜单
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

export interface MenuItem {
  key: string
  title: string
  icon?: string
  projectScoped: boolean
}

/** 判断路由是否为项目级（路径含动态项目 ID 参数） */
function isProjectScoped(route: RouteRecordRaw): boolean {
  return route.path.includes(':id') || route.path.includes(':projectId')
}

/** 从路由配置中提取菜单项 */
function extractMenuItems(routes: RouteRecordRaw[]): MenuItem[] {
  const items: MenuItem[] = []
  for (const route of routes) {
    const meta = route.meta || {}
    // 没有标题或标记隐藏的路由不出现在菜单中
    if (!meta.title || meta.hideInMenu) continue

    // 接口测试的父路由（ApiTestLayout）只作为一个菜单项
    if (route.children && route.children.length > 0 && route.path.includes('api-')) {
      items.push({
        key: '/' + route.path,
        title: '接口测试',
        icon: meta.icon as string || 'ApiOutlined',
        projectScoped: isProjectScoped(route),
      })
      continue
    }

    items.push({
      key: '/' + route.path,
      title: meta.title as string,
      icon: meta.icon as string | undefined,
      projectScoped: isProjectScoped(route),
    })
  }
  return items
}

/**
 * 从路由派生菜单
 *
 * @param projectId 当前项目 ID（用于替换路径中的 :id / :projectId）
 */
export function useMenu(projectId?: () => number | string | undefined) {
  const router = useRouter()

  const menuItems = computed<MenuItem[]>(() => {
    // 找到主布局路由（path: '/'）的 children
    const layoutRoute = router.options.routes.find(r => r.path === '/')
    if (!layoutRoute || !layoutRoute.children) return []
    return extractMenuItems(layoutRoute.children)
  })

  /** 全局菜单（不依赖项目 ID） */
  const globalMenus = computed(() =>
    menuItems.value.filter(m => !m.projectScoped)
  )

  /** 项目级菜单（需要项目 ID） */
  const projectMenus = computed(() => {
    const pid = projectId?.()
    if (!pid) return []
    return menuItems.value
      .filter(m => m.projectScoped)
      .map(m => ({
        ...m,
        key: m.key.replace(':projectId', String(pid)).replace(':id', String(pid)),
      }))
  })

  return { menuItems, globalMenus, projectMenus }
}
