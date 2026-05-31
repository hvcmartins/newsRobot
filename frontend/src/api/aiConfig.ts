import client from './client'

export interface AIConfigRead {
  is_enabled: boolean
  provider: string
  api_key_set: boolean
  model: string | null
  base_url: string | null
}

export interface AIConfigUpdate {
  is_enabled: boolean
  provider: string
  api_key?: string | null
  model?: string | null
  base_url?: string | null
}

export const aiConfigApi = {
  get: () => client.get<AIConfigRead>('/api/ai-config').then(r => r.data),
  update: (data: AIConfigUpdate) => client.put<AIConfigRead>('/api/ai-config', data).then(r => r.data),
  test: () => client.post<{ ok: boolean; response?: string; error?: string }>('/api/ai-config/test').then(r => r.data),
}
