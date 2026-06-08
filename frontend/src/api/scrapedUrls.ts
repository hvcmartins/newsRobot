import client from './client'

export interface ScrapedUrlItem {
  id: number
  url: string
  source_id: number | null
  source_name: string | null
  scraped_at: string | null
  article_id: number | null
  article_archived: boolean | null
  article_enriched: boolean | null
}

export interface ScrapedUrlPage {
  total: number
  page: number
  size: number
  items: ScrapedUrlItem[]
}

export const scrapedUrlsApi = {
  list: (params: { tenant_id: number; source_id?: number; q?: string; page?: number; size?: number; sort_by?: string; sort_dir?: string; status_filter?: string }) =>
    client.get<ScrapedUrlPage>('/api/scraped-urls/', { params }).then((r) => r.data),

  add: (body: { tenant_id: number; url: string; source_id?: number | null }) =>
    client.post<ScrapedUrlItem>('/api/scraped-urls/', body).then((r) => r.data),

  delete: (id: number, tenantId: number, deleteArticle = false) =>
    client.delete<{ deleted: number; article_deleted: number }>(
      `/api/scraped-urls/${id}`,
      { params: { tenant_id: tenantId, delete_article: deleteArticle } }
    ).then((r) => r.data),

  bulkDelete: (ids: number[], tenantId: number, deleteArticles = false) =>
    client.post<{ deleted: number; articles_deleted: number }>(
      '/api/scraped-urls/bulk-delete',
      { ids, tenant_id: tenantId, delete_articles: deleteArticles },
    ).then((r) => r.data),

  clear: (tenantId: number, sourceId?: number) =>
    client.delete<{ deleted: number }>('/api/scraped-urls/', {
      params: { tenant_id: tenantId, ...(sourceId != null ? { source_id: sourceId } : {}) },
    }).then((r) => r.data),
}
