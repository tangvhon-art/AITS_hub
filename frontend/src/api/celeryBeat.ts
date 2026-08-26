import request from './request'

export interface BeatTask {
  id: number
  name: string
  task_key?: string
  task: string
  schedule_type: 'interval' | 'cron'
  schedule_expr: string
  queue: string
  args?: any[]
  kwargs?: Record<string, any>
  description?: string
  enabled: boolean
  last_run_at?: string | null
  total_run_count: number
  created_at?: string
  updated_at?: string
}

export interface BeatTaskListResponse {
  total: number
  page: number
  page_size: number
  items: BeatTask[]
}

export interface BeatTaskLog {
  id: number
  task_name: string
  task_key?: string
  task_id: string
  args?: any[]
  kwargs?: Record<string, any>
  queue?: string
  state: 'RUNNING' | 'SUCCESS' | 'FAILURE' | 'TIMEOUT'
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  exception?: string | null
  traceback?: string | null
  created_at?: string
}

export interface BeatTaskLogListResponse {
  total: number
  page: number
  page_size: number
  items: BeatTaskLog[]
}

export function getBeatTasks(params?: { page?: number; page_size?: number; keyword?: string }) {
  return request.get<BeatTaskListResponse>('/celery/beat/list', { params })
}

export function createBeatTask(data: Partial<BeatTask>) {
  return request.post<BeatTask>('/celery/beat/create', data)
}

export function updateBeatTask(data: Partial<BeatTask>) {
  return request.put<BeatTask>('/celery/beat/update', data)
}

export function deleteBeatTask(id: number) {
  return request.delete<{ message: string }>(`/celery/beat/delete?id=${id}`)
}

export function setBeatTaskStatus(id: number, enabled: boolean) {
  return request.patch<BeatTask>('/celery/beat/status', { id, enabled })
}

export function runBeatTaskOnce(id: number) {
  return request.post<{ message: string; task_id: string }>('/celery/beat/run-once', { id })
}

export function getBeatTaskLogs(params?: {
  page?: number
  page_size?: number
  task_name?: string
  state?: string
  start_time?: string
  end_time?: string
}) {
  return request.get<BeatTaskLogListResponse>('/celery/beat/logs', { params })
}

export function getBeatTaskLogDetail(taskId: string) {
  return request.get<BeatTaskLog>(`/celery/beat/log-detail/${taskId}`)
}
