import request from './request'

export interface Project {
  id: number
  name: string
  description: string
  owner_id: number
  created_at: string
}

export function getProjects() {
  return request.get<Project[]>('/projects')
}

export function createProject(data: { name: string; description: string }) {
  return request.post<Project>('/projects', data)
}

export function updateProject(id: number, data: { name?: string; description?: string }) {
  return request.put<Project>(`/projects/${id}`, data)
}

export function deleteProject(id: number) {
  return request.delete(`/projects/${id}`)
}
