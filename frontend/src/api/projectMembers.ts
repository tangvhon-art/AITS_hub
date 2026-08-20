import request from './request'

export interface ProjectMember {
  id: number
  project_id: number
  user_id: number
  username: string
  full_name: string
  email: string
  role: string
  joined_at: string
}

export interface UserSearchResult {
  id: number
  username: string
  email: string
  full_name: string
}

export function getMembers(projectId: number) {
  return request.get<ProjectMember[]>(`/projects/${projectId}/members`)
}

export function searchUsers(projectId: number, q: string) {
  return request.get<UserSearchResult[]>(`/projects/${projectId}/members/search`, { params: { q } })
}

export function addMember(projectId: number, data: { user_id: number; role: string }) {
  return request.post<ProjectMember>(`/projects/${projectId}/members`, data)
}

export function updateMemberRole(projectId: number, userId: number, role: string) {
  return request.put<ProjectMember>(`/projects/${projectId}/members/${userId}`, { role })
}

export function removeMember(projectId: number, userId: number) {
  return request.delete(`/projects/${projectId}/members/${userId}`)
}
