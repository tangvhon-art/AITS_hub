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

/** 分页查询参数（新调用） */
export interface PromptListQuery {
  category?: string
  keyword?: string
  page?: number
  page_size?: number
}

/** 列表查询结果：分页模式返回对象，全量模式返回数组 */
export type PromptListResult = Prompt[] | { items: Prompt[]; total: number; page: number; page_size: number }

/** 兼容旧调用：传分类字符串 → 全量数组 */
function listPrompts(params: string): Promise<Prompt[]>
/** 新调用：传分页参数对象 → 分页对象或全量数组 */
function listPrompts(params?: PromptListQuery): Promise<PromptListResult>
function listPrompts(params?: PromptListQuery | string): Promise<PromptListResult> {
  const body = typeof params === 'string' ? { category: params } : (params ?? {})
  return request.post<PromptListResult>('/prompts/search', body)
}

/**
 * promptsApi 兼容对象
 * list 支持两种模式（后端 search 端点兼容）：
 * - 传分类字符串（如 'case_generation'）→ 返回全量数组（旧页面直接消费）
 * - 传 { category, keyword, page, page_size } → 返回分页对象 {items, total, page, page_size}
 * create/update/delete 委托给 BaseAPI 全局方法。
 */
export const promptsApi = {
  list: listPrompts,

  create: (data: PromptCreate) =>
    promptApi.createGlobal(data),

  update: (promptId: number, data: PromptUpdate) =>
    promptApi.updateGlobal(promptId, data),

  delete: (promptId: number) =>
    promptApi.removeGlobal(promptId),

  seedDefaults: () =>
    request.post<{ detail: string; count: number }>('/prompts/seed-defaults'),
}
