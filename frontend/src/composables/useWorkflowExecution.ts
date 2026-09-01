/**
 * 工作流执行方式高级 composable
 *
 * 封装 useWorkflowBackend 的常用模式，减少业务页面重复代码。
 * 业务页面只需调用 init() 初始化，提交时调用 getBackendParam() 获取参数。
 *
 * 使用示例：
 * ```typescript
 * const { showBackendOption, backend, init, getBackendParam, reset } = useWorkflowExecution('case.generate')
 *
 * // onMounted 中
 * init(projectId)
 *
 * // 提交时
 * const params = {
 *   ...otherParams,
 *   backend: getBackendParam(),
 * }
 * ```
 */
import { ref } from 'vue'
import { useWorkflowBackend } from '@/composables/useWorkflowBackend'

export function useWorkflowExecution(moduleId: string) {
  const { showBackendOption, defaultBackend, fetch } = useWorkflowBackend()
  const backend = ref('local')
  const loaded = ref(false)

  /** 初始化：查询模块配置并设置默认执行方式 */
  async function init(projectId?: number) {
    try {
      await fetch(moduleId, projectId)
      backend.value = defaultBackend.value || 'local'
      loaded.value = true
    } catch {
      // 查询失败则默认 local，不展示选项
      backend.value = 'local'
      loaded.value = false
    }
  }

  /** 获取提交用的 backend 参数（仅当展示选项且选择了 workflow 时返回） */
  function getBackendParam(): string | undefined {
    if (!showBackendOption.value) return undefined
    return backend.value
  }

  /** 重置为默认值（弹窗关闭时调用） */
  function reset() {
    backend.value = defaultBackend.value || 'local'
  }

  return {
    showBackendOption,
    backend,
    loaded,
    init,
    getBackendParam,
    reset,
  }
}
