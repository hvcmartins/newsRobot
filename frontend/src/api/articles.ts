import client from './client'
import type { Article, ArticleListResponse } from './types'

export interface ArticleFilters {
  tenant_id: number
  source_id?: number
  keyword?: string
  category?: string
  from_date?: string
  to_date?: string
  is_read?: boolean
  page?: number
  size?: number
}

export const articleApi = {
  list: (filters: ArticleFilters) =>
    client.get<ArticleListResponse>('/api/articles/', { params: filters }).then((r) => r.data),
  get: (id: number) => client.get<Article>(`/api/articles/${id}`).then((r) => r.data),
  markRead: (id: number) =>
    client.patch<Article>(`/api/articles/${id}/read`).then((r) => r.data),
  markAllRead: (tenantId: number) =>
    client.patch('/api/articles/read-all', null, { params: { tenant_id: tenantId } }).then((r) => r.data),
  delete: (id: number) => client.delete(`/api/articles/${id}`),
  clearAll: (tenantId: number) =>
    client.delete('/api/articles/', { params: { tenant_id: tenantId } }).then((r) => r.data),
  enrichmentStatus: (tenantId: number) =>
    client.get<{ total: number; enriched: number; pending: number; paused: boolean; tokens_per_second: number | null; seconds_per_article: number | null }>(
      '/api/articles/enrichment-status', { params: { tenant_id: tenantId } }
    ).then((r) => r.data),
  triggerEnrich: (tenantId: number, force = false) =>
    client.post<{ queued: number }>(
      '/api/articles/enrich', null, { params: { tenant_id: tenantId, force } }
    ).then((r) => r.data),
  stopEnrich: (tenantId: number) =>
    client.post<{ paused: true }>('/api/articles/enrich-stop', null, { params: { tenant_id: tenantId } }).then((r) => r.data),
}
