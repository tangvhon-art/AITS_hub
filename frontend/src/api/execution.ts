import request from './request'
import { streamSSE } from '@/utils/sse'

export function runExecution(projectId: number, data: {
  instruction: string
  target_url: string
  case_id?: number
  llm_config_id?: number
  headless?: boolean
}) {
  return request.post(`/projects/${projectId}/execution/run`, data)
}

export function getExecutionRuns(projectId: number, caseId?: number) {
  return request.get(`/projects/${projectId}/execution/runs`, { params: { case_id: caseId } })
}

export function getExecutionRun(projectId: number, runId: number) {
  return request.get(`/projects/${projectId}/execution/runs/${runId}`)
}

/**
 * SSE 流式执行（统一走 utils/sse.ts）
 * @returns AbortController，可调用 .abort() 中断
 */
export function streamExecution(
  projectId: number,
  data: { instruction: string; target_url: string; headless?: boolean; llm_config_id?: number; case_id?: number },
  onMessage: (event: any) => void,
  onError?: (error: any) => void,
  onDone?: () => void
) {
  return streamSSE(
    `/projects/${projectId}/execution/run`,
    {
      onMessage,
      onError,
      onDone,
    },
    { method: 'POST', body: data },
  )
}
