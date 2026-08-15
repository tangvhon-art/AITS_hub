import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getProjects, type Project } from '@/api/projects'

/**
 * 项目全局状态 Store
 *
 * 统一项目 ID 解析，消除各页面重复的：
 *   const projectId = Number(route.params.id)
 *   const projectId = Number(route.params.projectId)
 *
 * 用法：
 *   const projectStore = useProjectStore()
 *   projectStore.resolveProjectId(route)  // 从路由解析并缓存
 *   projectStore.currentProjectId         // 响应式当前项目 ID
 *   await projectStore.ensureProjects()   // 加载项目列表
 */
export const useProjectStore = defineStore('project', () => {
  /** 当前项目 ID（从路由解析或手动设置） */
  const currentProjectId = ref<number>(0)
  /** 当前项目名称 */
  const currentProjectName = ref<string>('')
  /** 项目列表 */
  const projects = ref<Project[]>([])
  /** 项目列表是否已加载 */
  const loaded = ref(false)

  /** 当前项目对象 */
  const currentProject = computed(() =>
    projects.value.find(p => p.id === currentProjectId.value) || null
  )

  /**
   * 从路由参数解析项目 ID。
   * 支持 :id 和 :projectId 两种参数名。
   */
  function resolveProjectId(route: { params: Record<string, any> }): number {
    const raw = route.params.projectId ?? route.params.id
    const id = Number(raw) || 0
    if (id && id !== currentProjectId.value) {
      currentProjectId.value = id
      // 同步更新项目名称（如果项目列表已加载）
      const proj = projects.value.find(p => p.id === id)
      if (proj) {
        currentProjectName.value = proj.name
      }
    }
    return id
  }

  /** 设置当前项目（手动切换时使用） */
  function setCurrentProject(id: number, name?: string) {
    currentProjectId.value = id
    if (name) {
      currentProjectName.value = name
    } else {
      const proj = projects.value.find(p => p.id === id)
      currentProjectName.value = proj?.name || ''
    }
  }

  /** 加载项目列表（带缓存） */
  async function ensureProjects(force = false): Promise<Project[]> {
    if (loaded.value && !force) {
      return projects.value
    }
    try {
      const res = await getProjects()
      projects.value = Array.isArray(res) ? res : (res as any)?.items || []
      loaded.value = true
      // 同步当前项目名称
      if (currentProjectId.value) {
        const proj = projects.value.find(p => p.id === currentProjectId.value)
        if (proj) {
          currentProjectName.value = proj.name
        }
      }
    } catch (e) {
      console.error('加载项目列表失败', e)
    }
    return projects.value
  }

  /** 根据 ID 获取项目名称 */
  function getProjectName(id: number): string {
    return projects.value.find(p => p.id === id)?.name || `项目#${id}`
  }

  return {
    currentProjectId,
    currentProjectName,
    currentProject,
    projects,
    loaded,
    resolveProjectId,
    setCurrentProject,
    ensureProjects,
    getProjectName,
  }
})
