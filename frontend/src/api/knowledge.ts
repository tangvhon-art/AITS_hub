import request from './request'

export interface KnowledgeDoc {
  id?: number
  project_id: number
  title: string
  content?: string
  file_type?: string
  file_path?: string
  chunk_count?: number
  status?: string
  error_message?: string
  created_by?: number
  created_at?: string
  updated_at?: string
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

export function getKnowledgeDocs(projectId: number, params?: { page?: number; page_size?: number }) {
  return request.post<KnowledgeDocListResponse>(`/projects/${projectId}/knowledge/search`, params)
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

export function searchKnowledge(projectId: number, query: string, topK = 5) {
  return request.post<KnowledgeSearchResult>(`/projects/${projectId}/knowledge/search`, { query, top_k: topK })
}

export function getKnowledgeStats(projectId: number) {
  return request.get<KnowledgeStats>(`/projects/${projectId}/knowledge/stats`)
}
