import request from './request'

export interface KnowledgeDoc {
  id?: number
  project_id: number
  title: string
  content?: string
  file_type?: string
  file_path?: string
  file_size?: number
  source_type?: string
  source_id?: number
  chunk_count?: number
  chunk_strategy?: string
  chunk_size?: number
  overlap?: number
  status?: string
  error_message?: string
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface KnowledgeChunk {
  id: number
  doc_id: number
  project_id?: number
  chunk_index: number
  content: string
  token_count: number
  doc_title: string
  created_at?: string
}

export interface KnowledgeChunkListResponse {
  total: number
  page: number
  page_size: number
  items: KnowledgeChunk[]
}

export interface KnowledgeDocListResponse {
  total: number
  page: number
  page_size: number
  items: KnowledgeDoc[]
}

export interface KnowledgeSearchResult {
  query: string
  results: Array<{
    doc_id: number
    title: string
    content: string
    chunk_index: number
    score: number
    similarity: number
  }>
  total: number
}

export interface KnowledgeStats {
  project_id: number
  total_docs: number
  total_chunks: number
}

export function getKnowledgeDocs(projectId: number, params?: { page?: number; page_size?: number; keyword?: string; source_type?: string }) {
  return request.post<KnowledgeDocListResponse>(`/projects/${projectId}/knowledge/docs/search`, params)
}

export function getKnowledgeChunks(projectId: number, params: { page?: number; page_size?: number; keyword?: string; doc_id?: number }) {
  return request.post<KnowledgeChunkListResponse>(`/projects/${projectId}/knowledge/chunks/search`, params)
}

export function syncRequirementsToKnowledge(projectId: number, requirementIds?: number[]) {
  return request.post<{ synced: number; doc_ids: number[]; message: string }>(
    `/projects/${projectId}/knowledge/sync-requirements`,
    requirementIds?.length ? requirementIds : [],
  )
}

export function getKnowledgeDoc(projectId: number, docId: number) {
  return request.get<KnowledgeDoc>(`/projects/${projectId}/knowledge/${docId}`)
}

export function createKnowledgeDoc(projectId: number, data: { title: string; content: string; file_type?: string }) {
  return request.post<KnowledgeDoc>(`/projects/${projectId}/knowledge`, data)
}

export function uploadKnowledgeDoc(projectId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<KnowledgeDoc>(`/projects/${projectId}/knowledge/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteKnowledgeDoc(projectId: number, docId: number) {
  return request.delete(`/projects/${projectId}/knowledge/${docId}`)
}

export function generateChunks(projectId: number, docId: number) {
  return request.post<{ doc_id: number; status: string; message: string }>(
    `/projects/${projectId}/knowledge/${docId}/generate-chunks`,
  )
}

export function searchKnowledge(projectId: number, query: string, topK = 5) {
  return request.post<KnowledgeSearchResult>(`/projects/${projectId}/knowledge/search`, { query, top_k: topK })
}

export function getKnowledgeStats(projectId: number) {
  return request.get<KnowledgeStats>(`/projects/${projectId}/knowledge/stats`)
}
