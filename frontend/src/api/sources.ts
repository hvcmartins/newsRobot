import client from './client'
import type { Source } from './types'

export const sourceApi = {
  list: (tenantId: number) =>
    client.get<Source[]>('/api/sources/', { params: { tenant_id: tenantId } }).then((r) => r.data),
  create: (data: Partial<Source>) =>
    client.post<Source>('/api/sources/', data).then((r) => r.data),
  update: (id: number, data: Partial<Source>) =>
    client.put<Source>(`/api/sources/${id}`, data).then((r) => r.data),
  delete: (id: number) => client.delete(`/api/sources/${id}`),
  test: (id: number) =>
    client.post<{ source_name: string; articles_found: number; sample: unknown[] }>(
      `/api/sources/${id}/test`
    ).then((r) => r.data),
}
