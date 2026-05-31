import React, { useState } from 'react'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import type { Source } from '@/api/types'

interface Props {
  initial?: Partial<Source>
  onSave: (data: Partial<Source>) => Promise<void>
  onClose: () => void
}

export default function SourceForm({ initial, onSave, onClose }: Props) {
  const [form, setForm] = useState<Partial<Source>>({
    name: '', url: '', type: 'rss', css_selector: '', keywords: '[]', is_active: true,
    ...initial,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (patch: Partial<Source>) => setForm((f) => ({ ...f, ...patch }))

  const handleSave = async () => {
    if (!form.name?.trim() || !form.url?.trim()) {
      setError('Name and URL are required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave(form)
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={initial?.id ? 'Edit Source' : 'Add Source'} onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Input label="Name" value={form.name ?? ''} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. TechCrunch" />
        <Input label="URL" value={form.url ?? ''} onChange={(e) => set({ url: e.target.value })} placeholder="https://..." />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Type</label>
          <select
            value={form.type ?? 'rss'}
            onChange={(e) => set({ type: e.target.value as 'rss' | 'scrape' })}
            style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
          >
            <option value="rss">RSS Feed</option>
            <option value="scrape">Web Scrape</option>
          </select>
        </div>

        {form.type === 'scrape' && (
          <Input
            label="CSS Selector"
            value={form.css_selector ?? ''}
            onChange={(e) => set({ css_selector: e.target.value })}
            placeholder="e.g. article.post, .news-item"
          />
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Keywords (comma-separated, overrides global)</label>
          <input
            value={(() => {
              try { return JSON.parse(form.keywords ?? '[]').join(', ') } catch { return '' }
            })()}
            onChange={(e) => {
              const kws = e.target.value.split(',').map((k) => k.trim()).filter(Boolean)
              set({ keywords: JSON.stringify(kws) })
            }}
            placeholder="Leave empty to use tenant global keywords"
            style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
          />
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={form.is_active ?? true} onChange={(e) => set({ is_active: e.target.checked })} />
          <span style={{ fontSize: 13 }}>Active</span>
        </label>

        {error && <p style={{ fontSize: 12, color: '#e53935' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={saving} onClick={handleSave}>Save</Button>
        </div>
      </div>
    </Modal>
  )
}
