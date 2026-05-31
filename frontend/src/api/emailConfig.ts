import client from './client'
import type { EmailConfig } from './types'

export const emailApi = {
  get: (tenantId: number) =>
    client.get<EmailConfig>(`/api/email-config/${tenantId}`).then((r) => r.data),
  create: (data: Partial<EmailConfig>) =>
    client.post<EmailConfig>('/api/email-config/', data).then((r) => r.data),
  update: (tenantId: number, data: Partial<EmailConfig>) =>
    client.patch<EmailConfig>(`/api/email-config/${tenantId}`, data).then((r) => r.data),
  testSend: (tenantId: number) =>
    client.post<{ sent_to: string }>(`/api/email-config/${tenantId}/test`).then((r) => r.data),
  previewUrl: (tenantId: number) => `/api/email-config/${tenantId}/preview`,
}
