import client from './client'
import type { Tenant } from './types'

export const tenantApi = {
  list: () => client.get<Tenant[]>('/api/tenants/').then((r) => r.data),
  get: (slug: string) => client.get<Tenant>(`/api/tenants/${slug}`).then((r) => r.data),
  create: (data: Partial<Tenant>) =>
    client.post<Tenant>('/api/tenants/', data).then((r) => r.data),
  update: (slug: string, data: Partial<Tenant>) => {
    if (!slug) return Promise.reject(new Error('Cannot save: tenant has no slug. Rebuild the container to auto-repair.'))
    return client.patch<Tenant>(`/api/tenants/${slug}`, data).then((r) => r.data)
  },
  delete: (slug: string) => client.delete(`/api/tenants/${slug}`),
  pauseScrape: (slug: string) =>
    client.post<Tenant>(`/api/tenants/${slug}/pause-scrape`).then((r) => r.data),
  resumeScrape: (slug: string) =>
    client.post<Tenant>(`/api/tenants/${slug}/resume-scrape`).then((r) => r.data),
  suggestKeywords: (slug: string) =>
    client.post<{ keywords: string[] }>(`/api/tenants/${slug}/suggest-keywords`).then((r) => r.data),
  suggestCategories: (slug: string) =>
    client.post<{ categories: string[] }>(`/api/tenants/${slug}/suggest-categories`).then((r) => r.data),
}
