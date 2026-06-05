import client from './client'
import type { Source } from './types'

export interface SourceCheckResult {
  id: number
  online: boolean
  http_status?: number
  error?: string
}

export const sourceApi = {
  list: (tenantId: number) =>
    client.get<Source[]>('/api/sources/', { params: { tenant_id: tenantId } }).then((r) => r.data),
  create: (data: Partial<Source>) =>
    client.post<Source>('/api/sources/', data).then((r) => r.data),
  update: (id: number, data: Partial<Source>) =>
    client.patch<Source>(`/api/sources/${id}`, data).then((r) => r.data),
  delete: (id: number) => client.delete(`/api/sources/${id}`),
  test: (id: number) =>
    client.post<{ source_name: string; articles_found: number; sample: unknown[] }>(
      `/api/sources/${id}/test`
    ).then((r) => r.data),
  checkAll: (tenantId: number) =>
    client.post<{ results: SourceCheckResult[] }>(
      '/api/sources/check-all', null, { params: { tenant_id: tenantId } }
    ).then((r) => r.data),
  scrapeNow: (sourceId: number) =>
    client.post(`/api/scrape-runs/trigger/${sourceId}`).then((r) => r.data),
  scrapeAllNow: (tenantId: number) =>
    client.post(`/api/scrape-runs/trigger`, null, { params: { tenant_id: tenantId } }).then((r) => r.data),
  clearScrapedUrls: (sourceId: number) =>
    client.delete<{ cleared: number }>(`/api/sources/${sourceId}/scraped-urls`).then((r) => r.data),
  importCsv: (tenantId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return client
      .post<{ imported: number; skipped: number; errors: number; rows: CsvImportRows }>(
        `/api/sources/import-csv`,
        fd,
        { params: { tenant_id: tenantId }, headers: { 'Content-Type': 'multipart/form-data' } },
      )
      .then((r) => r.data)
  },
}

export interface CsvImportRows {
  imported: { name: string; url: string; type: string }[]
  skipped:  { row: number; name: string; url: string }[]
  errors:   { row: number; name?: string; error: string }[]
}
