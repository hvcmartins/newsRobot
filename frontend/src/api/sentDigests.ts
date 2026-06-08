import client from './client'
import type { SentDigestListResponse } from './types'

export const sentDigestApi = {
  list: (tenantId: number, page = 1, size = 30) =>
    client.get<SentDigestListResponse>('/api/sent-digests/', {
      params: { tenant_id: tenantId, page, size },
    }).then((r) => r.data),
}
