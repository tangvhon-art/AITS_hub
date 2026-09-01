/**
 * 工作流后端配置查询 composable
 *
 * 业务页面（需求生成/功能点拆分/用例生成/用例评审）调用，决定是否展示"执行方式"单选。
 * 当 workflow_available=true（全局开关开启 + 模块配置了连接+external_agent_id）时，
 * 在提交弹窗展示 local/workflow 单选；否则隐藏。
 */
import { ref, type Ref } from 'vue'
import { getEffectiveBackend, type WorkflowEffectiveConfig } from '@/api/workflow'

export interface UseWorkflowBackendResult {
  config: Ref<WorkflowEffectiveConfig | null>
  loading: Ref<boolean>
  /** 是否在页面展示"执行方式"单选（仅当模块允许页面切换 + workflow 可用时） */
  showBackendOption: Ref<boolean>
  /** 默认执行后端 local/workflow */
  defaultBackend: Ref<string>
  fetch: (module_id: string, project_id?: number) => Promise<void>
}

export function useWorkflowBackend(): UseWorkflowBackendResult {
  const config = ref<WorkflowEffectiveConfig | null>(null)
  const loading = ref(false)

  const showBackendOption = ref(false)
  const defaultBackend = ref('local')

  async function fetch(module_id: string, project_id?: number) {
    loading.value = true
    try {
      const cfg = await getEffectiveBackend(module_id, project_id)
      config.value = cfg
      // 仅当模块允许页面切换 + workflow 可用时展示选项
      showBackendOption.value = !!(cfg.page_selectable && cfg.workflow_available)
      defaultBackend.value = cfg.default_backend || 'local'
    } catch {
      // 查询失败（接口未启用/无权限）则不展示选项，默认 local
      config.value = null
      showBackendOption.value = false
      defaultBackend.value = 'local'
    } finally {
      loading.value = false
    }
  }

  return { config, loading, showBackendOption, defaultBackend, fetch }
}
