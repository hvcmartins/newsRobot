import client from './client'
import type { Tenant } from './types'

export const tenantApi = {
  list: () => client.get<Tenant[]>('/api/tenants/').then((r) => r.data),
  get: (slug: string) => client.get<Tenant>(`/api/tenants/${slug}`).then((r) => r.data),
  create: (data: Partial<Tenant>) =>
    client.post<Tenant>('/api/tenants/', data).then((r) => r.data),
  update: (slug: string, data: Partial<Tenant>) =>
    client.patch<Tenant>(`/api/tenants/${slug}`, data).then((r) => r.data),
  delete: (slug: string) => client.delete(`/api/tenants/${slug}`),
  suggestKeywords: (slug: string) =>
    client.post<{ keywords: string[] }>(`/api/tenants/${slug}/suggest-keywords`).then((r) => r.data),
}
