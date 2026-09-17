import request from './request'

export interface CaseSuite {
  id: number
  project_id: number
  name: string
  description: string
  case_count: number
  module_count: number
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface CaseSuiteList {
  items: CaseSuite[]
  total: number
  page: number
  page_size: number
}

/** 用例集列表（支持名称搜索、分页） */
export function getCaseSuites(projectId: number, params?: { name?: string; page?: number; page_size?: number }) {
  return request.get<CaseSuiteList>(`/projects/${projectId}/case-suites`, { params })
}

/** 新建用例集 */
export function createCaseSuite(projectId: number, data: { name: string; description?: string }) {
  return request.post<CaseSuite>(`/projects/${projectId}/case-suites`, data)
}

/** 编辑用例集 */
export function updateCaseSuite(projectId: number, suiteId: number, data: { name?: string; description?: string }) {
  return request.put<CaseSuite>(`/projects/${projectId}/case-suites/${suiteId}`, data)
}

/** 删除用例集（仅删关联关系，不影响用例） */
export function deleteCaseSuite(projectId: number, suiteId: number) {
  return request.delete(`/projects/${projectId}/case-suites/${suiteId}`)
}

/** 集合内用例列表 */
export function getSuiteCases(
  projectId: number,
  suiteId: number,
  params?: { module?: string; priority?: string; req_id?: number; page?: number; page_size?: number },
) {
  return request.get<any>(`/projects/${projectId}/case-suites/${suiteId}/cases`, { params })
}

/** 批量加入用例：按用例ID / 需求ID / 模块名（可组合） */
export function addCasesToSuite(
  projectId: number,
  suiteId: number,
  data: { case_ids?: number[]; req_ids?: number[]; module_names?: string[] },
) {
  return request.post<{ message: string; added: number; matched: number }>(
    `/projects/${projectId}/case-suites/${suiteId}/cases`,
    data,
  )
}

/** 批量移除用例 */
export function removeCasesFromSuite(projectId: number, suiteId: number, caseIds: number[]) {
  return request.delete<{ message: string; removed: number }>(`/projects/${projectId}/case-suites/${suiteId}/cases`, {
    data: { case_ids: caseIds },
  })
}

/** 导图树数据 */
export function getSuiteMind(projectId: number, suiteId: number) {
  return request.get<any>(`/projects/${projectId}/case-suites/${suiteId}/mind`)
}

/** 更新用例集内用例的执行状态（upsert） */
export function updateCaseExecStatus(projectId: number, suiteId: number, caseId: number, execStatus: string) {
  return request.put(`/projects/${projectId}/case-suites/${suiteId}/cases/${caseId}/exec-status`, {
    exec_status: execStatus,
  })
}

/** 按用例集导出 .xmind 文件 */
export function exportSuiteXmind(projectId: number, suiteId: number) {
  return request.get(`/projects/${projectId}/case-suites/${suiteId}/export-xmind`, { responseType: 'blob' })
}

/** 添加用例数据源：项目全部用例 */
export function getAvailableCases(
  projectId: number,
  params?: { module?: string; priority?: string; keyword?: string; req_id?: number; page?: number; page_size?: number },
) {
  return request.get<any>(`/projects/${projectId}/case-suites/available-cases`, { params })
}
