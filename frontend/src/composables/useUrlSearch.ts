import { useRoute, useRouter } from 'vue-router'

/**
 * URL 查询状态持久化 composable（已停用）
 *
 * 筛选条件改为仅在前端内存中维护，不再同步到 URL query params。
 * 保留函数签名以兼容现有调用方，但 loadFromUrl 直接返回默认值，syncToUrl 为空操作。
 */
export function useUrlSearch() {
  const route = useRoute()
  const router = useRouter()

  function loadFromUrl<T extends Record<string, any>>(fields: T): T {
    return { ...fields }
  }

  function syncToUrl(_params: Record<string, any>) {
    // no-op: 不再将筛选条件写入 URL
  }

  return { loadFromUrl, syncToUrl, route, router }
}
