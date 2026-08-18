import request from './request'

export interface Skill {
  id: number
  name: string
  title: string
  description: string
  category: string
  version: string
  author: string
  source: 'builtin' | 'manual' | 'imported'
  trigger_config: Record<string, any>
  skill_config: Record<string, any>
  prompts: Record<string, string>
  scripts: Record<string, string>
  files: Record<string, string>
  icon_path: string
  is_active: boolean
  is_builtin: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface SkillList {
  total: number
  items: Skill[]
}

export const skillsApi = {
  list: (params?: { page?: number; page_size?: number; category?: string; source?: string; is_active?: boolean }) =>
    request.get<SkillList>('/skills', { params }),

  create: (data: Partial<Skill>) =>
    request.post<Skill>('/skills', data),

  update: (id: number, data: Partial<Skill>) =>
    request.put<Skill>(`/skills/${id}`, data),

  remove: (id: number) =>
    request.delete(`/skills/${id}`),

  toggle: (id: number) =>
    request.post<Skill>(`/skills/${id}/toggle`),

  match: (message: string, project_id?: number) =>
    request.post<{ matched: boolean; skill: Skill | null; reason: string }>('/skills/match', { message, project_id }),

  execute: (id: number, data: { message: string; project_id?: number; user_id?: number }) =>
    `/skills/${id}/execute`,

  importSkill: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request.post<{ id: number; name: string; title: string; version: string; source: string; warnings: string[]; success: boolean; message: string }>(
      '/skills/import', form, { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },

  importText: (content: string) =>
    request.post<{ id: number; name: string; title: string; version: string; source: string; warnings: string[]; success: boolean; message: string }>(
      '/skills/import-text', { content }
    ),

  exportUrl: (id: number) => `/skills/${id}/export`,
}
