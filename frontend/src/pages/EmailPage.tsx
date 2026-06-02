import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { emailApi } from '@/api/emailConfig'
import type { EmailConfig } from '@/api/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

type Freq = 'immediate' | 'daily' | 'weekly'

const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const
const DAY_LABEL: Record<string, string> = {
  monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu',
  friday: 'Fri', saturday: 'Sat', sunday: 'Sun',
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function DigestWindowSection({ form, set }: { form: Partial<EmailConfig>; set: (p: Partial<EmailConfig>) => void }) {
  const overrides: Record<string, number> = (() => {
    try { return JSON.parse(form.schedule_overrides ?? '{}') } catch { return {} }
  })()

  const setOverride = (day: string, val: string) => {
    const next = { ...overrides }
    if (val === '' || val === '0') {
      delete next[day]
    } else {
      const n = parseInt(val, 10)
      if (!isNaN(n) && n > 0) next[day] = n
    }
    set({ schedule_overrides: Object.keys(next).length ? JSON.stringify(next) : null })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Digest Window</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type="number" min={1} max={720}
          value={form.lookback_hours ?? 24}
          onChange={(e) => set({ lookback_hours: Math.max(1, parseInt(e.target.value) || 24) })}
          style={{ width: 64, padding: '5px 8px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
        />
        <span style={{ fontSize: 13, color: '#666' }}>hours per digest (default for all days)</span>
      </div>
      <p style={{ fontSize: 11, color: '#999', margin: 0 }}>
        Override specific days — useful for Monday covering the weekend (72 h = Fri + Sat + Sun).
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {WEEKDAYS.map((day) => (
          <div key={day} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
            <span style={{ fontSize: 11, color: '#777', fontWeight: 500 }}>{DAY_LABEL[day]}</span>
            <input
              type="number" min={1} max={720} placeholder="—"
              value={overrides[day] ?? ''}
              onChange={(e) => setOverride(day, e.target.value)}
              style={{
                width: 52, padding: '4px 6px', border: '1px solid #ddd', borderRadius: 6,
                fontSize: 12, textAlign: 'center',
                background: overrides[day] ? '#f0f4ff' : '#fff',
                borderColor: overrides[day] ? '#c7d8fb' : '#ddd',
              }}
            />
            {overrides[day] && (
              <span style={{ fontSize: 10, color: '#3a5fbb' }}>{overrides[day]}h</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function EmailPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const tenantId = activeTenant?.id ?? 0

  const { data: existing, isLoading } = useQuery({
    queryKey: ['email-config', tenantId],
    queryFn: () => emailApi.get(tenantId).catch(() => null),
    enabled: !!tenantId,
  })

  const [form, setForm] = useState<Partial<EmailConfig>>({
    smtp_host: '', smtp_port: 587, smtp_user: '', smtp_password: '',
    from_email: '', from_name: 'News Robot',
    recipients_json: '[]', frequency: 'daily', send_time: '08:00',
    lookback_hours: 24, schedule_overrides: '{"monday":72}',
    subject_template: '{{tenant_name}} News Digest – {{date}}',
    intro_text: '', is_active: true,
    monthly_digest_enabled: false, monthly_digest_day: 1, monthly_digest_time: '08:00',
    yearly_digest_enabled: false, yearly_digest_month: 1, yearly_digest_day: 1, yearly_digest_time: '08:00',
  })
  const [recipientInput, setRecipientInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [testMsg, setTestMsg] = useState<string | null>(null)
  const [sendNowConfirm, setSendNowConfirm] = useState(false)

  useEffect(() => {
    if (existing) setForm({ ...existing, smtp_password: '' })
  }, [existing])

  const set = (patch: Partial<EmailConfig>) => setForm((f) => ({ ...f, ...patch }))

  const recipients: string[] = (() => {
    try { return JSON.parse(form.recipients_json ?? '[]') } catch { return [] }
  })()

  const addRecipient = () => {
    const email = recipientInput.trim()
    if (!email || recipients.includes(email)) return
    set({ recipients_json: JSON.stringify([...recipients, email]) })
    setRecipientInput('')
  }

  const removeRecipient = (email: string) => {
    set({ recipients_json: JSON.stringify(recipients.filter((r) => r !== email)) })
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const payload = { ...form, tenant_id: tenantId }
      if (existing) {
        await emailApi.update(tenantId, payload)
      } else {
        await emailApi.create(payload)
      }
      qc.invalidateQueries({ queryKey: ['email-config', tenantId] })
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const testMut = useMutation({
    mutationFn: () => emailApi.testSend(tenantId),
    onSuccess: (data) => setTestMsg(`Test email sent to ${data.sent_to}`),
    onError: (e: Error) => setTestMsg(`Error: ${e.message}`),
  })

  const sendNowMut = useMutation({
    mutationFn: () => emailApi.sendNow(tenantId),
    onSuccess: () => {
      setTestMsg('Digest sent successfully — articles moved to archive.')
      setSendNowConfirm(false)
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
      qc.invalidateQueries({ queryKey: ['archive', tenantId] })
      qc.invalidateQueries({ queryKey: ['dashboard', tenantId] })
    },
    onError: (e: Error) => {
      setTestMsg(`Error: ${e.message}`)
      setSendNowConfirm(false)
    },
  })

  if (!activeTenant) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Email Settings</h1>
        {existing && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {sendNowConfirm ? (
              <>
                <span style={{ fontSize: 12, color: '#333' }}>Send digest now and archive all pending articles?</span>
                <Button loading={sendNowMut.isPending} onClick={() => sendNowMut.mutate()}
                  style={{ background: 'var(--brand-color)', borderColor: 'var(--brand-color)' }}>
                  Send Now
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setSendNowConfirm(false)}>Cancel</Button>
              </>
            ) : (
              <Button onClick={() => setSendNowConfirm(true)}
                style={{ background: 'var(--brand-color)', borderColor: 'var(--brand-color)' }}>
                📤 Send Digest Now
              </Button>
            )}
          </div>
        )}
      </div>

      {testMsg && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, fontSize: 13,
          background: testMsg.startsWith('Error') ? '#fdecea' : '#e8f5e9',
          color: testMsg.startsWith('Error') ? '#c62828' : '#2e7d32',
          border: `1px solid ${testMsg.startsWith('Error') ? '#f5c6cb' : '#c8e6c9'}`,
        }}>
          {testMsg}
          <button onClick={() => setTestMsg(null)} style={{ marginLeft: 12, background: 'none', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: 14 }}>×</button>
        </div>
      )}

      {isLoading ? <p style={{ color: '#999' }}>Loading…</p> : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>
          {/* Config form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* SMTP */}
            <div style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>SMTP Configuration</h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px', gap: 10 }}>
                <Input label="SMTP Host" value={form.smtp_host ?? ''} onChange={(e) => set({ smtp_host: e.target.value })} placeholder="smtp.gmail.com" />
                <Input label="Port" type="number" value={form.smtp_port ?? 587} onChange={(e) => set({ smtp_port: Number(e.target.value) })} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <Input label="Username" value={form.smtp_user ?? ''} onChange={(e) => set({ smtp_user: e.target.value })} />
                <Input label="Password" type="password" value={form.smtp_password ?? ''} onChange={(e) => set({ smtp_password: e.target.value })} placeholder="Leave blank to keep current" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <Input label="From Email" value={form.from_email ?? ''} onChange={(e) => set({ from_email: e.target.value })} />
                <Input label="From Name" value={form.from_name ?? ''} onChange={(e) => set({ from_name: e.target.value })} />
              </div>
            </div>

            {/* Regular Schedule */}
            <div style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>Regular Digest Schedule</h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Frequency</label>
                  <select value={form.frequency ?? 'daily'} onChange={(e) => set({ frequency: e.target.value as Freq })}
                    style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}>
                    <option value="immediate">Immediate (high-relevance only)</option>
                    <option value="daily">Daily Digest</option>
                    <option value="weekly">Weekly Summary</option>
                  </select>
                </div>
                <Input label="Send Time (UTC)" type="time" value={form.send_time ?? '08:00'} onChange={(e) => set({ send_time: e.target.value })} />
              </div>
              {form.frequency !== 'immediate' && <DigestWindowSection form={form} set={set} />}
              <Input label="Subject Template" value={form.subject_template ?? ''} onChange={(e) => set({ subject_template: e.target.value })}
                placeholder="{{tenant_name}} News Digest – {{date}}" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Intro Text (optional)</label>
                <textarea value={form.intro_text ?? ''} onChange={(e) => set({ intro_text: e.target.value })}
                  rows={2} placeholder="Intro paragraph shown at the top of the email…"
                  style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }} />
              </div>
            </div>

            {/* Monthly Digest */}
            <div style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Monthly Digest</h2>
                  <p style={{ fontSize: 12, color: '#888', margin: '4px 0 0' }}>AI-generated narrative summary of the past month's news.</p>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.monthly_digest_enabled ?? false}
                    onChange={(e) => set({ monthly_digest_enabled: e.target.checked })}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 500 }}>Enabled</span>
                </label>
              </div>
              {form.monthly_digest_enabled && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Day of month</label>
                    <input
                      type="number" min={1} max={28}
                      value={form.monthly_digest_day ?? 1}
                      onChange={(e) => set({ monthly_digest_day: Math.min(28, Math.max(1, parseInt(e.target.value) || 1)) })}
                      style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
                    />
                    <span style={{ fontSize: 11, color: '#999' }}>1–28 (sent summarizing previous month)</span>
                  </div>
                  <Input label="Send Time (UTC)" type="time" value={form.monthly_digest_time ?? '08:00'}
                    onChange={(e) => set({ monthly_digest_time: e.target.value })} />
                </div>
              )}
            </div>

            {/* Yearly Digest */}
            <div style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Yearly Digest</h2>
                  <p style={{ fontSize: 12, color: '#888', margin: '4px 0 0' }}>AI-generated year-in-review synthesizing monthly summaries.</p>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.yearly_digest_enabled ?? false}
                    onChange={(e) => set({ yearly_digest_enabled: e.target.checked })}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 500 }}>Enabled</span>
                </label>
              </div>
              {form.yearly_digest_enabled && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Month</label>
                    <select
                      value={form.yearly_digest_month ?? 1}
                      onChange={(e) => set({ yearly_digest_month: parseInt(e.target.value) })}
                      style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
                    >
                      {MONTHS.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Day</label>
                    <input
                      type="number" min={1} max={28}
                      value={form.yearly_digest_day ?? 1}
                      onChange={(e) => set({ yearly_digest_day: Math.min(28, Math.max(1, parseInt(e.target.value) || 1)) })}
                      style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
                    />
                  </div>
                  <Input label="Send Time (UTC)" type="time" value={form.yearly_digest_time ?? '08:00'}
                    onChange={(e) => set({ yearly_digest_time: e.target.value })} />
                </div>
              )}
            </div>

            {/* Recipients */}
            <div style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>Recipients</h2>
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={recipientInput} onChange={(e) => setRecipientInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') addRecipient() }}
                  placeholder="email@company.com"
                  style={{ flex: 1, padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }} />
                <Button size="sm" variant="secondary" onClick={addRecipient}>Add</Button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {recipients.map((r) => (
                  <span key={r} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#f0f2f5', borderRadius: 16, padding: '3px 10px', fontSize: 12 }}>
                    {r}
                    <button onClick={() => removeRecipient(r)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#999', fontSize: 14, lineHeight: 1 }}>×</button>
                  </span>
                ))}
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={form.is_active ?? true} onChange={(e) => set({ is_active: e.target.checked })} />
                <span style={{ fontSize: 13 }}>Active</span>
              </label>

              {saveError && <p style={{ fontSize: 12, color: '#e53935', margin: 0 }}>{saveError}</p>}

              <div style={{ display: 'flex', gap: 8 }}>
                <Button variant="secondary" loading={testMut.isPending} onClick={() => testMut.mutate()} disabled={!existing}>
                  Send Test Email
                </Button>
                <Button loading={saving} onClick={handleSave}>Save</Button>
              </div>
            </div>
          </div>

          {/* Email preview */}
          <div style={{ background: '#fff', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', position: 'sticky', top: 24 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Email Preview</h2>
            {existing ? (
              <iframe
                src={emailApi.previewUrl(tenantId)}
                style={{ width: '100%', height: 640, border: '1px solid #eee', borderRadius: 6 }}
                title="Email preview"
              />
            ) : (
              <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', border: '1px solid #eee', borderRadius: 6 }}>
                Save config first to see preview
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
