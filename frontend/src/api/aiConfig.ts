import client from './client'

export interface AIConfigRead {
  is_enabled: boolean
  provider: string
  api_key_set: boolean
  model: string | null
  base_url: string | null
  local_model_id: string | null
  cpu_limit_percent?: number
  n_gpu_layers?: number
  serper_api_key_set: boolean
  google_search_api_key_set: boolean
  google_search_cx: string | null
}

export interface AIConfigUpdate {
  is_enabled: boolean
  provider: string
  api_key?: string | null
  model?: string | null
  base_url?: string | null
  local_model_id?: string | null
  cpu_limit_percent?: number
  n_gpu_layers?: number
  serper_api_key?: string | null
  google_search_api_key?: string | null
  google_search_cx?: string | null
}

export interface LocalModel {
  id: string
  name: string
  tag: string
  description: string
  size_gb: number
  ram_gb: number
  status: 'not_downloaded' | 'downloading' | 'ready' | 'error' | 'unknown'
  progress: number
  error?: string | null
}

export const aiConfigApi = {
  get: () => client.get<AIConfigRead>('/api/ai-config').then(r => r.data),
  update: (data: AIConfigUpdate) => client.patch<AIConfigRead>('/api/ai-config', data).then(r => r.data),
  test: () => client.post<{ ok: boolean; response?: string; error?: string }>('/api/ai-config/test').then(r => r.data),
  listLocalModels: () => client.get<LocalModel[]>('/api/ai-config/local-models').then(r => r.data),
  getLocalModel: (id: string) => client.get<LocalModel>(`/api/ai-config/local-models/${id}`).then(r => r.data),
  downloadLocalModel: (id: string) => client.post(`/api/ai-config/local-models/${id}/download`).then(r => r.data),
  deleteLocalModel: (id: string) => client.delete(`/api/ai-config/local-models/${id}`).then(r => r.data),
}
