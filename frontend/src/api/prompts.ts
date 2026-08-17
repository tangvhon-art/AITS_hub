import request from './request'
import { BaseAPI } from './base'

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

/** BaseAPI 实例：全局 Prompt 资源 */
export const promptApi = new BaseAPI<Prompt, PromptCreate, PromptUpdate>('/prompts', { global: true })

/**
 * 兼容旧接口：promptsApi 对象
 * list 返回非分页列表（后端特性），保留自定义实现；
 * create/update/delete 委托给 BaseAPI 全局方法。
 */
export const promptsApi = {
  list: (category?: string) =>
    request.post<Prompt[]>('/prompts/search', category ? { category } : {}),

  create: (data: PromptCreate) =>
    promptApi.createGlobal(data),

  update: (promptId: number, data: PromptUpdate) =>
    promptApi.updateGlobal(promptId, data),

  delete: (promptId: number) =>
    promptApi.removeGlobal(promptId),

  seedDefaults: () =>
    request.post<{ detail: string; count: number }>('/prompts/seed-defaults'),
}
