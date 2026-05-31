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
}
