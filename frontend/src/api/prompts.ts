import request from './request'

export interface Prompt {
  id: number
  name: string
  description: string
  category: string
  system_prompt: string
  user_prompt_template: string
  variables: any[]
  is_default: boolean
  status: string
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface PromptCreate {
  name: string
  description?: string
  category?: string
  system_prompt: string
  user_prompt_template?: string
  variables?: any[]
  is_default?: boolean
  status?: string
}

export interface PromptUpdate {
  name?: string
  description?: string
  category?: string
  system_prompt?: string
  user_prompt_template?: string
  variables?: any[]
  is_default?: boolean
  status?: string
}

export const promptsApi = {
  list: (category?: string) =>
    request.get<Prompt[]>('/prompts', { params: category ? { category } : {} }),

  create: (data: PromptCreate) =>
    request.post<Prompt>('/prompts', data),

  update: (promptId: number, data: PromptUpdate) =>
    request.put<Prompt>(`/prompts/${promptId}`, data),

  delete: (promptId: number) =>
    request.delete(`/prompts/${promptId}`),

  seedDefaults: () =>
    request.post<{ detail: string; count: number }>('/prompts/seed-defaults'),
}
