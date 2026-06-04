import React, { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { tenantApi } from '@/api/tenants'
import { articleApi } from '@/api/articles'
import type { Tenant } from '@/api/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'pt', label: 'Portuguese' },
  { code: 'fr', label: 'French' },
  { code: 'de', label: 'German' },
  { code: 'es', label: 'Spanish' },
  { code: 'it', label: 'Italian' },
  { code: 'nl', label: 'Dutch' },
  { code: 'ja', label: 'Japanese' },
  { code: 'ko', label: 'Korean' },
  { code: 'zh', label: 'Chinese' },
  { code: 'ar', label: 'Arabic' },
  { code: 'ru', label: 'Russian' },
]

export default function TenantSettingsPage() {
  const { activeTenant, refreshTenants } = useTenant()
  const qc = useQueryClient()

  const [form, setForm] = useState<Partial<Tenant>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [suggestingKw, setSuggestingKw] = useState(false)
  const [suggestingCats, setSuggestingCats] = useState(false)
  const [editingCatIdx, setEditingCatIdx] = useState<number | null>(null)
  const [editCatValue, setEditCatValue] = useState('')
  const [addCatValue, setAddCatValue] = useState('')
  const [dragCatIdx, setDragCatIdx] = useState<number | null>(null)
  const [dragOverCatIdx, setDragOverCatIdx] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [addingTenant, setAddingTenant] = useState(false)
  const [newTenant, setNewTenant] = useState({ name: '', slug: '', primary_color: '#0066cc' })

  // Danger zone confirmation states
  const [resetConfirm, setResetConfirm] = useState<'queue' | 'archive' | 'scraped-urls' | null>(null)

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

  const acceptedLangs: string[] = (() => {
    try { return JSON.parse(form.accepted_languages ?? '[]') } catch { return [] }
  })()

  const toggleLang = (code: string) => {
    const next = acceptedLangs.includes(code)
      ? acceptedLangs.filter((l) => l !== code)
      : [...acceptedLangs, code]
    set({ accepted_languages: next.length ? JSON.stringify(next) : null })
  }

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
        max_article_age_days: form.max_article_age_days ?? null,
        accepted_languages: form.accepted_languages ?? null,
        translation_language: form.translation_language ?? null,
        ai_categories: form.ai_categories ?? null,
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

  const resetQueueMut = useMutation({
    mutationFn: () => articleApi.resetQueue(activeTenant!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles', activeTenant!.id] })
      qc.invalidateQueries({ queryKey: ['enrichment-status', activeTenant!.id] })
      qc.invalidateQueries({ queryKey: ['dashboard', activeTenant!.id] })
      setResetConfirm(null)
    },
  })

  const resetArchiveMut = useMutation({
    mutationFn: () => articleApi.resetArchive(activeTenant!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['archive', activeTenant!.id] })
      qc.invalidateQueries({ queryKey: ['dashboard', activeTenant!.id] })
      setResetConfirm(null)
    },
  })

  const resetScrapedUrlsMut = useMutation({
    mutationFn: () => articleApi.resetScrapedUrls(activeTenant!.id),
    onSuccess: () => {
      setResetConfirm(null)
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

  const setCategories = (cats: string[]) =>
    set({ ai_categories: cats.length ? JSON.stringify(cats) : null })

  const addCategory = (val: string) => {
    const trimmed = val.trim()
    if (!trimmed || categories.includes(trimmed)) return
    setCategories([...categories, trimmed])
    setAddCatValue('')
  }

  const removeCategory = (idx: number) =>
    setCategories(categories.filter((_, i) => i !== idx))

  const startEditCat = (idx: number) => {
    setEditingCatIdx(idx)
    setEditCatValue(categories[idx])
  }

  const dropCat = (targetIdx: number) => {
    if (dragCatIdx === null || dragCatIdx === targetIdx) return
    const next = [...categories]
    const [moved] = next.splice(dragCatIdx, 1)
    next.splice(targetIdx, 0, moved)
    setCategories(next)
    setDragCatIdx(null)
    setDragOverCatIdx(null)
  }

  const commitEditCat = () => {
    if (editingCatIdx === null) return
    const trimmed = editCatValue.trim()
    if (trimmed && !categories.some((c, i) => c === trimmed && i !== editingCatIdx)) {
      const next = [...categories]
      next[editingCatIdx] = trimmed
      setCategories(next)
    }
    setEditingCatIdx(null)
    setEditCatValue('')
  }

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
          ⚠ This tenant has no slug — saves will fail until you rebuild the container.
        </div>
      )}

      {/* General */}
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Max article age (days)</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="number" min={1} max={3650}
              value={form.max_article_age_days ?? ''}
              onChange={(e) => set({ max_article_age_days: e.target.value ? Math.max(1, parseInt(e.target.value)) : null })}
              placeholder="30"
              style={{ width: 80, padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
            />
            <span style={{ fontSize: 12, color: '#888' }}>
              Articles older than this are ignored during scraping.{' '}
              {!form.max_article_age_days && <span style={{ color: '#bbb' }}>Using server default (30 days).</span>}
            </span>
          </div>
        </div>
      </section>

      {/* Language Settings */}
      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>Language Settings</h2>
        <p style={{ fontSize: 13, color: '#666' }}>
          Select which article languages to accept. Articles in other languages will have their AI summary translated.
          Leave empty to accept all languages without translation.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Accepted Languages</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {LANGUAGES.map(({ code, label }) => {
              const active = acceptedLangs.includes(code)
              return (
                <button
                  key={code}
                  onClick={() => toggleLang(code)}
                  style={{
                    padding: '5px 12px', borderRadius: 16, fontSize: 12, fontWeight: 500,
                    cursor: 'pointer', border: '1px solid',
                    background: active ? 'var(--brand-color)' : '#fff',
                    borderColor: active ? 'var(--brand-color)' : '#ddd',
                    color: active ? '#fff' : '#555',
                    transition: 'all 0.15s',
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>
          {acceptedLangs.length === 0 && (
            <p style={{ fontSize: 11, color: '#bbb', margin: 0 }}>All languages accepted — no translation will occur.</p>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Translation Language</label>
          <p style={{ fontSize: 11, color: '#888', margin: 0 }}>
            When an article's language is not in the accepted list, translate its AI summary into this language.
          </p>
          <select
            value={form.translation_language ?? ''}
            onChange={(e) => set({ translation_language: e.target.value || null })}
            style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, maxWidth: 220 }}
          >
            <option value="">None (keep original)</option>
            {LANGUAGES.map(({ code, label }) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </div>
      </section>

      {/* AI Topic Profile */}
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
          <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>Article Categories</label>
          {/* Interactive tag editor */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
            padding: '7px 10px', border: '1px solid #ddd', borderRadius: 8,
            background: '#fafafa', minHeight: 44, cursor: 'text',
          }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                (e.currentTarget.querySelector('input[placeholder]') as HTMLInputElement)?.focus()
              }
            }}
          >
            {categories.map((c, i) =>
              editingCatIdx === i ? (
                <input
                  key={i}
                  autoFocus
                  value={editCatValue}
                  onChange={(e) => setEditCatValue(e.target.value)}
                  onBlur={commitEditCat}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); commitEditCat() }
                    if (e.key === 'Escape') { setEditingCatIdx(null); setEditCatValue('') }
                  }}
                  style={{
                    border: '1px solid var(--brand-color)', borderRadius: 12,
                    padding: '3px 8px', fontSize: 12, outline: 'none', color: '#3a5fbb',
                    width: Math.max(80, editCatValue.length * 8 + 16),
                    background: '#fff',
                  }}
                />
              ) : (
                <span
                  key={c}
                  draggable
                  onDragStart={() => { setDragCatIdx(i); setEditingCatIdx(null) }}
                  onDragOver={(e) => { e.preventDefault(); setDragOverCatIdx(i) }}
                  onDrop={() => dropCat(i)}
                  onDragEnd={() => { setDragCatIdx(null); setDragOverCatIdx(null) }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    background: dragCatIdx === i ? '#e8efff' : '#f0f4ff',
                    border: `1px solid ${dragOverCatIdx === i && dragCatIdx !== i ? 'var(--brand-color)' : '#c7d8fb'}`,
                    borderRadius: 12, padding: '3px 6px 3px 8px',
                    fontSize: 12, color: '#3a5fbb', userSelect: 'none',
                    cursor: 'grab',
                    opacity: dragCatIdx === i ? 0.5 : 1,
                    outline: dragOverCatIdx === i && dragCatIdx !== i ? '2px solid var(--brand-color)' : 'none',
                  }}
                >
                  <span style={{ fontSize: 10, color: '#aac', marginRight: 2, cursor: 'grab' }} title="Drag to reorder">⠿</span>
                  <span
                    onClick={() => startEditCat(i)}
                    style={{ cursor: 'text' }}
                    title="Click to rename"
                  >{c}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeCategory(i) }}
                    title="Remove"
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      padding: '0 2px', lineHeight: 1, color: '#93b4f0',
                      fontSize: 15, display: 'flex', alignItems: 'center',
                    }}
                  >×</button>
                </span>
              )
            )}
            <input
              value={addCatValue}
              onChange={(e) => setAddCatValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault()
                  addCategory(addCatValue)
                }
                if (e.key === 'Backspace' && !addCatValue && categories.length > 0) {
                  removeCategory(categories.length - 1)
                }
              }}
              onBlur={() => { if (addCatValue.trim()) addCategory(addCatValue) }}
              placeholder={categories.length === 0 ? 'Add a category and press Enter…' : 'Add…'}
              style={{
                border: 'none', background: 'transparent', fontSize: 12,
                color: '#555', outline: 'none', minWidth: 120, flex: 1, padding: '3px 4px',
              }}
            />
          </div>
          <p style={{ fontSize: 11, color: '#aaa', margin: 0 }}>
            Drag to reorder · click label to rename · × to remove · Enter or comma to add
          </p>
          <Button variant="secondary" size="sm" loading={suggestingCats} onClick={suggestCategories}
            disabled={!form.topic_profile?.trim()}>
            ✦ Generate Categories from Profile
          </Button>
        </div>

        <hr style={{ border: 'none', borderTop: '1px solid #eee', margin: '4px 0' }} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontSize: 12, color: '#888' }}>
            Saves all settings on this page.
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {saved && <span style={{ fontSize: 12, color: '#2e7d32' }}>✓ Saved</span>}
            {saveError && <span style={{ fontSize: 12, color: '#e53935' }}>{saveError}</span>}
            <Button loading={saveMut.isPending} onClick={() => saveMut.mutate()}>Save Settings</Button>
          </div>
        </div>
      </section>

      {/* Add New Company */}
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

      {/* Danger Zone */}
      <section style={{ background: '#fff', borderRadius: 10, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.07)', border: '1px solid #ffcdd2' }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#c62828', marginBottom: 16 }}>Danger Zone</h2>

        {/* Reset Queue */}
        <div style={{ borderBottom: '1px solid #ffeaea', paddingBottom: 16, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Reset News Queue</div>
              <div style={{ fontSize: 12, color: '#666' }}>Delete all pending (non-archived) articles from the queue.</div>
            </div>
            {resetConfirm === 'queue' ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#c62828' }}>Delete all pending articles?</span>
                <Button size="sm" variant="danger" loading={resetQueueMut.isPending} onClick={() => resetQueueMut.mutate()}>
                  Confirm
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setResetConfirm(null)}>Cancel</Button>
              </div>
            ) : (
              <Button size="sm" variant="danger" onClick={() => setResetConfirm('queue')}>Reset Queue</Button>
            )}
          </div>
        </div>

        {/* Reset Archive */}
        <div style={{ borderBottom: '1px solid #ffeaea', paddingBottom: 16, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Reset Archive</div>
              <div style={{ fontSize: 12, color: '#666' }}>Delete all archived articles and sent digest records.</div>
            </div>
            {resetConfirm === 'archive' ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#c62828' }}>Delete all archived articles?</span>
                <Button size="sm" variant="danger" loading={resetArchiveMut.isPending} onClick={() => resetArchiveMut.mutate()}>
                  Confirm
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setResetConfirm(null)}>Cancel</Button>
              </div>
            ) : (
              <Button size="sm" variant="danger" onClick={() => setResetConfirm('archive')}>Reset Archive</Button>
            )}
          </div>
        </div>

        {/* Reset Scraped URLs */}
        <div style={{ borderBottom: '1px solid #ffeaea', paddingBottom: 16, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Reset Scraped URL History</div>
              <div style={{ fontSize: 12, color: '#666' }}>Clear deduplication history — previously seen URLs will be re-scraped on next run.</div>
            </div>
            {resetConfirm === 'scraped-urls' ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#c62828' }}>Clear URL history?</span>
                <Button size="sm" variant="danger" loading={resetScrapedUrlsMut.isPending} onClick={() => resetScrapedUrlsMut.mutate()}>
                  Confirm
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setResetConfirm(null)}>Cancel</Button>
              </div>
            ) : (
              <Button size="sm" variant="danger" onClick={() => setResetConfirm('scraped-urls')}>Reset URL History</Button>
            )}
          </div>
        </div>

        {/* Delete Tenant */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#c62828', marginBottom: 4 }}>Delete Tenant</div>
          <p style={{ fontSize: 12, color: '#666', marginBottom: 10 }}>
            Permanently delete <strong>{activeTenant.name}</strong> and all its data. Type the tenant name to confirm.
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
        </div>
      </section>
    </div>
  )
}
