import request from './request'

export function exportCases(projectId: number, requirementIds?: number[]) {
  const params: Record<string, string> = {}
  if (requirementIds && requirementIds.length > 0) {
    params.requirement_ids = requirementIds.join(',')
  }
  return request.get(`/projects/${projectId}/data/cases/export`, {
    responseType: 'blob',
    params
  })
}

export function exportCasesXmind(projectId: number, requirementIds?: number[]) {
  const params: Record<string, string> = {}
  if (requirementIds && requirementIds.length > 0) {
    params.requirement_ids = requirementIds.join(',')
  }
  return request.get(`/projects/${projectId}/data/cases/export-xmind`, {
    responseType: 'blob',
    params
  })
}

export function importCases(projectId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/projects/${projectId}/data/cases/import`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function downloadTemplate(projectId: number) {
  return request.get(`/projects/${projectId}/data/cases/template`, {
    responseType: 'blob'
  })
}
