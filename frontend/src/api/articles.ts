import client from './client'
import type { Article, ArticleListResponse, DashboardStats } from './types'

export interface ArticleFilters {
  tenant_id: number
  source_id?: number
  keyword?: string
  category?: string
  from_date?: string
  to_date?: string
  is_read?: boolean
  archived?: boolean
  digest_id?: number
  undigested?: boolean
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
  reEnrich: (id: number) =>
    client.post<{ queued: boolean }>(`/api/articles/${id}/re-enrich`).then((r) => r.data),
  fetchImage: (id: number) =>
    client.post<{ image_url: string | null }>(`/api/articles/${id}/fetch-image`).then((r) => r.data),
  fetchMissingImages: (tenantId: number) =>
    client.post<{ queued: number }>('/api/articles/fetch-missing-images', null, { params: { tenant_id: tenantId } }).then((r) => r.data),
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
  categories: (tenantId: number) =>
    client.get<{ categories: string[] }>('/api/articles/categories', { params: { tenant_id: tenantId } }).then((r) => r.data.categories),
  dashboard: (tenantId: number) =>
    client.get<DashboardStats>('/api/articles/dashboard', { params: { tenant_id: tenantId } }).then((r) => r.data),
  resetQueue: (tenantId: number) =>
    client.delete('/api/articles/reset/queue', { params: { tenant_id: tenantId } }).then((r) => r.data),
  resetArchive: (tenantId: number) =>
    client.delete('/api/articles/reset/archive', { params: { tenant_id: tenantId } }).then((r) => r.data),
  resetScrapedUrls: (tenantId: number) =>
    client.delete('/api/articles/reset/scraped-urls', { params: { tenant_id: tenantId } }).then((r) => r.data),
  resetQueueForRescrape: (tenantId: number) =>
    client.post<{ deleted_articles: number; cleared_urls: number }>(
      '/api/articles/reset/queue-for-rescrape', null, { params: { tenant_id: tenantId } }
    ).then((r) => r.data),
}
