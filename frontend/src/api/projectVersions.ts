import request from './request'

export interface ProjectVersion {
  id?: number
  project_id?: number
  name: string
  description?: string
  status?: string
  start_date?: string | null
  end_date?: string | null
  released_at?: string | null
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface VersionListResponse {
  total: number
  page: number
  page_size: number
  items: ProjectVersion[]
}

export function getVersions(projectId: number, params?: { status?: string; page?: number; page_size?: number }) {
  return request.get<VersionListResponse>(`/projects/${projectId}/versions`, { params })
}

export function createVersion(projectId: number, data: ProjectVersion) {
  return request.post<ProjectVersion>(`/projects/${projectId}/versions`, data)
}

export function getVersion(projectId: number, versionId: number) {
  return request.get<ProjectVersion>(`/projects/${projectId}/versions/${versionId}`)
}

export function updateVersion(projectId: number, versionId: number, data: Partial<ProjectVersion>) {
  return request.put<ProjectVersion>(`/projects/${projectId}/versions/${versionId}`, data)
}

export function deleteVersion(projectId: number, versionId: number) {
  return request.delete(`/projects/${projectId}/versions/${versionId}`)
}
