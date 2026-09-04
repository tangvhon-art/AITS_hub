import request from './request'

export interface MCPConnector {
  id: number
  name: string
  description: string
  transport: 'sse' | 'stdio' | 'http'
  url: string
  command: string
  args: string[]
  env_vars: Record<string, string>
  status: string
  tools_count: number
  tools_list: Array<{ name: string; description: string }>
  last_connected_at: string | null
  error_message: string
  is_active: boolean
  created_at: string
}

export interface MCPConnectorList {
  total: number
  items: MCPConnector[]
}

export const mcpApi = {
  list: (params?: { page?: number; page_size?: number; status?: string; keyword?: string }) =>
    request.get<MCPConnectorList>('/mcp/connectors', { params }),

  create: (data: Partial<MCPConnector>) =>
    request.post<MCPConnector>('/mcp/connectors', data),

  update: (id: number, data: Partial<MCPConnector>) =>
    request.put<MCPConnector>(`/mcp/connectors/${id}`, data),

  remove: (id: number) =>
    request.delete(`/mcp/connectors/${id}`),

  connect: (id: number) =>
    request.post<{ success: boolean; message: string; tools_count: number; tools: any[] }>(`/mcp/connectors/${id}/connect`),

  disconnect: (id: number) =>
    request.post(`/mcp/connectors/${id}/disconnect`),

  getTools: (id: number) =>
    request.get<{ tools: any[]; count: number }>(`/mcp/connectors/${id}/tools`),

  listAllTools: () =>
    request.get<{ total: number; tools: any[] }>('/mcp/tools'),
}
