import client from './client'
import type { CatalogSource, Source } from './types'

export const catalogApi = {
  list: (params?: { category?: string; language?: string; country?: string; q?: string }) =>
    client.get<CatalogSource[]>('/api/catalog/', { params }).then((r) => r.data),
  categories: () => client.get<string[]>('/api/catalog/categories').then((r) => r.data),
  addToTenant: (catalogId: number, tenantId: number) =>
    client
      .post<Source>(`/api/catalog/${catalogId}/add`, null, { params: { tenant_id: tenantId } })
      .then((r) => r.data),
  isInTenant: (catalogId: number, tenantId: number) =>
    client
      .get<{ added: boolean; source_id: number | null }>(
        `/api/catalog/${catalogId}/in-tenant/${tenantId}`
      )
      .then((r) => r.data),
  recommend: (tenantId: number) =>
    client
      .post<{ recommended: CatalogSource[] }>('/api/catalog/recommend', null, {
        params: { tenant_id: tenantId },
      })
      .then((r) => r.data),
}
