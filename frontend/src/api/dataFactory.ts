import request from './request'
import { dataPoolsApi } from './dataPools'

/** 工具参数 Schema（与后端 ToolParameter 同构） */
export interface ToolParamSchema {
  type: string
  properties: Record<string, any>
  required: string[]
}

/** 工具元信息 */
export interface DataToolMeta {
  name: string
  title: string
  description: string
  parameters: ToolParamSchema
  is_generator: boolean
}

/** 工具分类 */
export interface DataToolCategory {
  key: string
  title: string
  icon: string
  tools: DataToolMeta[]
}

/** 统一执行结果（生成类：{ count, result }；转换类：{ ... }） */
export interface ToolResult {
  count?: number
  result?: any
  [key: string]: any
}

export const dataFactoryApi = {
  /** 获取六类工具分类与参数 Schema */
  getCategories: () =>
    request.get<{ categories: DataToolCategory[]; total: number }>('/data-factory/categories'),

  /** 统一工具执行入口 */
  runTool: (toolName: string, params: Record<string, any>) =>
    request.post<{ tool: string; result: ToolResult }>(`/data-factory/tools/${toolName}`, params),

  /** 批量执行 */
  runBatch: (items: { tool: string; params: Record<string, any> }[]) =>
    request.post<{ tool: string; ok: boolean; result?: ToolResult; error?: any }[]>(
      '/data-factory/batch',
      items,
    ),

  /** 生成结果一键导入 Mock 数据池（生成 static 型数据池） */
  importToPool: (projectId: number, name: string, data: any[]) =>
    dataPoolsApi.create(projectId, { name, data, data_type: 'static' }),
}
