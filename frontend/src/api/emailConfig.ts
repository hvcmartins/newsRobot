import client from './client'
import type { EmailConfig } from './types'

export const emailApi = {
  get: (tenantId: number) =>
    client.get<EmailConfig>(`/api/email-config/${tenantId}`).then((r) => r.data),
  create: (data: Partial<EmailConfig>) =>
    client.post<EmailConfig>('/api/email-config/', data).then((r) => r.data),
  update: (tenantId: number, data: Partial<EmailConfig>) =>
    client.patch<EmailConfig>(`/api/email-config/${tenantId}`, data).then((r) => r.data),
  pingSmtp: (tenantId: number) =>
    client.post<{ ok: boolean; host: string; port: number; status: string }>(`/api/email-config/${tenantId}/ping`).then((r) => r.data),
  testSend: (tenantId: number) =>
    client.post<{ sent_to: string; subject: string; smtp_host: string; smtp_port: number }>(
      `/api/email-config/${tenantId}/test`
    ).then((r) => r.data),
  diagnose: (tenantId: number) =>
    client.get<{
      smtp_host: string; smtp_port: number; smtp_user: string;
      smtp_password_set: boolean; from_email: string; recipients: string[];
      is_active: boolean; test_will_send_to: string;
    }>(`/api/email-config/${tenantId}/diagnose`).then((r) => r.data),
  sendNow: (tenantId: number) =>
    client.post<{ sent: boolean }>(`/api/email-config/${tenantId}/send-now`).then((r) => r.data),
  previewUrl: (tenantId: number) => `/api/email-config/${tenantId}/preview`,
}
