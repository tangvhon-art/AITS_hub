import request from './request'

export function runExecution(projectId: number, data: {
  instruction: string
  target_url: string
  case_id?: number
  llm_config_id?: number
  headless?: boolean
}) {
  return request.post<{ run_id: number; status: string; message: string }>(
    `/projects/${projectId}/execution/run`,
    data,
  )
}

export function getExecutionRunStatus(projectId: number, runId: number) {
  return request.get<{
    run_id: number
    status: string
    execution_log: any[]
    actual_result: string
    error_message: string
    duration: number
    screenshot_url: string
    completed: boolean
  }>(`/projects/${projectId}/execution/runs/${runId}/status`)
}

export function getExecutionRuns(projectId: number, caseId?: number) {
  return request.get(`/projects/${projectId}/execution/runs`, { params: { case_id: caseId } })
}

export function getExecutionRun(projectId: number, runId: number) {
  return request.get(`/projects/${projectId}/execution/runs/${runId}`)
}
