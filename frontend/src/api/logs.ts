import client from './client'

export interface LogEntry {
  id: number
  ts: string
  level: 'INFO' | 'WARNING' | 'ERROR'
  source: 'scraper' | 'scheduler' | 'ai' | 'email' | 'general'
  message: string
}

export const logsApi = {
  get: (since = 0) =>
    client.get<LogEntry[]>('/api/logs', { params: { since } }).then(r => r.data),
  clear: () => client.delete('/api/logs').then(r => r.data),
}
