import client from './client'
import type { ScrapeRunListResponse } from './types'

export const scrapeRunApi = {
  list: (tenantId: number, page = 1, size = 20) =>
    client
      .get<ScrapeRunListResponse>('/api/scrape-runs/', { params: { tenant_id: tenantId, page, size } })
      .then((r) => r.data),
  triggerFull: (tenantId: number) =>
    client.post('/api/scrape-runs/trigger', null, { params: { tenant_id: tenantId } }).then((r) => r.data),
  triggerSource: (sourceId: number) =>
    client.post(`/api/scrape-runs/trigger/${sourceId}`).then((r) => r.data),
}
