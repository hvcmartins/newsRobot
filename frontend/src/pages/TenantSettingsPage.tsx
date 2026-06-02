import React, { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { tenantApi } from '@/api/tenants'
import type { Tenant } from '@/api/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

export default function TenantSettingsPage() {
  const { activeTenant, refreshTenants } = useTenant()
  const qc = useQueryClient()

  const [form, setForm] = useState<Partial<Tenant>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [suggestingKw, setSuggestingKw] = useState(false)
  const [suggestingCats, setSuggestingCats] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [addingTenant, setAddingTenant] = useState(false)
  const [newTenant, setNewTenant] = useState({ name: '', slug: '', primary_color: '#0066cc' })

  useEffect(() => {
    if (activeTenant) {
      setForm({ ...activeTenant })
    }
  }, [activeTenant?.id])

  const set = (patch: Partial<Tenant>) => setForm((f) => ({ ...f, ...patch }))

  const keywords: string[] = (() => {
    try { return JSON.parse(form.global_keywords ?? '[]') } catch { return [] }
  })()

  const setKeywords = (kws: string[]) => set({ global_keywords: JSON.stringify(kws) })

  const saveMut = useMutation({
    mutationFn: async () => {
      if (!activeTenant) return
      await tenantApi.update(activeTenant.slug, {
        name: form.name,
        logo_url: form.logo_url,
        primary_color: form.primary_color,
        global_keywords: form.global_keywords,
        schedule_cron: form.schedule_cron,
        topic_profile: form.topic_profile,
      })
    },
    onSuccess: () => {
      refreshTenants()
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
    onError: (e: Error) => setSaveError(e.message),
  })

  const createMut = useMutation({
    mutationFn: () => tenantApi.create(newTenant),
    onSuccess: () => {
      refreshTenants()
      setAddingTenant(false)
      setNewTenant({ name: '', slug: '', primary_color: '#0066cc' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: () => tenantApi.delete(activeTenant!.slug),
    onSuccess: () => {
      refreshTenants()
      localStorage.removeItem('activeSlug')
    },
  })

  const suggestKeywords = async () => {
    if (!activeTenant) return
    setSuggestingKw(true)
    try {
      const { keywords: kws } = await tenantApi.suggestKeywords(activeTenant.slug)
      setKeywords(kws)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to suggest keywords')
    } finally {
      setSuggestingKw(false)
    }
  }

  const categories: string[] = (() => {
    try { return JSON.parse(form.ai_categories ?? '[]') } catch { return [] }
  })()

  const suggestCategories = async () => {
    if (!activeTenant) return
    setSuggestingCats(true)
    try {
      const { categories: cats } = await tenantApi.suggestCategories(activeTenant.slug)
      set({ ai_categories: JSON.stringify(cats) })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to generate categories')
    } finally {
      setSuggestingCats(false)
    }
  }

  if (!activeTenant) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 640 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Tenant Settings</h1>
      {!activeTenant.slug && (
        <div style={{ background: '#fff3e0', border: '1px solid #ffb74d', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#e65100' }}>
          ⚠ This tenant has no slug — saves will fail until you rebuild the container. The startup migration will auto-assign a slug from the company name.
        </div>
      )}

      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>General</h2>
        <Input label="Company Name" value={form.name ?? ''} onChange={(e) => set({ name: e.target.value })} />
        <Input label="Logo URL (optional)" value={form.logo_url ?? ''} onChange={(e) => set({ logo_url: e.target.value })} placeholder="https://..." />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Brand Color</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input type="color" value={form.primary_color ?? '#0066cc'} onChange={(e) => set({ primary_color: e.target.value })}
              style={{ width: 40, height: 36, border: '1px solid #ddd', borderRadius: 6, cursor: 'pointer', padding: 2 }} />
            <input value={form.primary_color ?? '#0066cc'} onChange={(e) => set({ primary_color: e.target.value })}
              style={{ width: 100, padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }} />
            <div style={{ width: 36, height: 36, borderRadius: 6, background: form.primary_color ?? '#0066cc' }} />
          </div>
        </div>

        <Input label="Scrape Schedule (cron)" value={form.schedule_cron ?? ''} onChange={(e) => set({ schedule_cron: e.target.value })}
          placeholder="0 * * * *  (hourly)" />
        <p style={{ fontSize: 11, color: '#999', marginTop: -8 }}>Cron format: minute hour day month weekday. E.g. "0 */2 * * *" = every 2 hours</p>
      </section>

      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>AI Topic Profile</h2>
        <p style={{ fontSize: 13, color: '#666' }}>Describe what news your company cares about. The AI uses this to filter and score articles.</p>
        <textarea
          value={form.topic_profile ?? ''}
          onChange={(e) => set({ topic_profile: e.target.value })}
          rows={5}
          placeholder="e.g. We are a fintech company focused on digital payments and open banking. We track regulatory changes in Europe, new payment technology, and major bank partnerships..."
          style={{ padding: '10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.6 }}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Global Keywords (fallback when AI is disabled)</label>
          <input
            value={keywords.join(', ')}
            onChange={(e) => setKeywords(e.target.value.split(',').map(k => k.trim()).filter(Boolean))}
            placeholder="fintech, payments, open banking..."
            style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
          />
          <Button variant="secondary" size="sm" loading={suggestingKw} onClick={suggestKeywords}
            disabled={!form.topic_profile?.trim()}>
            ✦ Generate Keywords from Profile
          </Button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Article Categories (derived from your profile)</label>
          {categories.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {categories.map(c => (
                <span key={c} style={{ background: '#f0f4ff', border: '1px solid #c7d8fb', borderRadius: 12, padding: '3px 10px', fontSize: 12, color: '#3a5fbb' }}>
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 12, color: '#aaa', margin: 0 }}>
              No categories yet — generate them from your profile below.
            </p>
          )}
          <Button variant="secondary" size="sm" loading={suggestingCats} onClick={suggestCategories}
            disabled={!form.topic_profile?.trim()}>
            ✦ Generate Categories from Profile
          </Button>
        </div>
        <hr style={{ border: 'none', borderTop: '1px solid #eee', margin: '4px 0' }} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontSize: 12, color: '#888' }}>
            Saves all settings on this page (general, branding, schedule and profile).
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {saved && <span style={{ fontSize: 12, color: '#2e7d32' }}>✓ Saved</span>}
            {saveError && <span style={{ fontSize: 12, color: '#e53935' }}>{saveError}</span>}
            <Button loading={saveMut.isPending} onClick={() => saveMut.mutate()}>Save Settings</Button>
          </div>
        </div>
      </section>

      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>Add New Company</h2>
        {addingTenant ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Input label="Name" value={newTenant.name} onChange={(e) => setNewTenant(t => ({ ...t, name: e.target.value }))} />
            <Input label="Slug (URL-safe ID)" value={newTenant.slug} onChange={(e) => setNewTenant(t => ({ ...t, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') }))} />
            {createMut.isError && (
              <p style={{ fontSize: 12, color: '#e53935' }}>{(createMut.error as Error)?.message}</p>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="secondary" onClick={() => setAddingTenant(false)}>Cancel</Button>
              <Button
                loading={createMut.isPending}
                disabled={!newTenant.name.trim() || !newTenant.slug.trim()}
                onClick={() => createMut.mutate()}
              >Create</Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setAddingTenant(true)}>+ Add Company</Button>
        )}
      </section>

      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', border: '1px solid #ffcdd2' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#c62828', marginBottom: 12 }}>Danger Zone</h2>
        <p style={{ fontSize: 13, color: '#666', marginBottom: 12 }}>
          Delete <strong>{activeTenant.name}</strong> and all its sources, articles, and email config.
          Type the tenant name to confirm.
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={activeTenant.name}
            style={{ flex: 1, padding: '7px 10px', border: '1px solid #ffcdd2', borderRadius: 6, fontSize: 13 }}
          />
          <Button
            variant="danger"
            disabled={deleteConfirm !== activeTenant.name}
            loading={deleteMut.isPending}
            onClick={() => deleteMut.mutate()}
          >
            Delete Tenant
          </Button>
        </div>
      </section>
    </div>
  )
}
