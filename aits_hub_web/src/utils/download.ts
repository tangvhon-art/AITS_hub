/**
 * 文件下载工具
 */

/**
 * 触发浏览器下载 Blob 数据
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

/**
 * 下载 JSON 文件
 */
export function downloadJSON(data: any, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  downloadBlob(blob, filename.endsWith('.json') ? filename : `${filename}.json`)
}

/**
 * 下载文本文件
 */
export function downloadText(text: string, filename: string, mimeType = 'text/plain'): void {
  const blob = new Blob([text], { type: mimeType })
  downloadBlob(blob, filename)
}

/**
 * 下载 CSV 文件
 */
export function downloadCSV(rows: (string | number)[][], filename: string): void {
  const csv = rows
    .map((row) =>
      row
        .map((cell) => {
          const str = String(cell ?? '')
          return str.includes(',') || str.includes('"') || str.includes('\n')
            ? `"${str.replace(/"/g, '""')}"`
            : str
        })
        .join(','),
    )
    .join('\n')
  // 添加 BOM 以支持 Excel 正确识别 UTF-8
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  downloadBlob(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`)
}

/**
 * 从 URL 下载文件
 */
export async function downloadFromURL(url: string, filename?: string): Promise<void> {
  const response = await fetch(url)
  const blob = await response.blob()
  const name = filename || response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'download'
  downloadBlob(blob, name)
}
