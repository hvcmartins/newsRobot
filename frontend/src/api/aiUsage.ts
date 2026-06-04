import client from './client'

export type AIUsageView = 'minute' | 'hour' | 'day'

export interface AIUsageBucket {
  ts: string       // ISO UTC string — bucket start time
  calls: number
  tokens_in: number
  tokens_out: number
}

export interface AIUsageResponse {
  buckets: AIUsageBucket[]
  today: { calls: number; tokens_in: number; tokens_out: number }
  today_db_calls: number  // persists across restarts
}

export const aiUsageApi = {
  get: (view: AIUsageView, tenantId?: number) =>
    client.get<AIUsageResponse>('/api/ai/usage', {
      params: { view, ...(tenantId ? { tenant_id: tenantId } : {}) },
    }).then(r => r.data),
}
