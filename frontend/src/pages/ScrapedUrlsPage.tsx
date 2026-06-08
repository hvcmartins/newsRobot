import React, { useState, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { useTenant } from '@/contexts/TenantContext'
import { scrapedUrlsApi } from '@/api/scrapedUrls'
import { sourceApi } from '@/api/sources'
import type { Source } from '@/api/types'

const PAGE_SIZE = 50

type SortBy = 'scraped_at' | 'source' | 'status'
type SortDir = 'asc' | 'desc'
type StatusFilter = '' | 'none' | 'pending' | 'queue' | 'archived'

// ── Add URL modal ─────────────────────────────────────────────────────────────
function AddUrlModal({
  tenantId,
  sources,
  onClose,
  onAdded,
}: {
  tenantId: number
  sources: Source[]
  onClose: () => void
  onAdded: () => void
}) {
  const [url, setUrl] = useState('')
  const [sourceId, setSourceId] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    const trimmed = url.trim()
    if (!trimmed.startsWith('http')) { setError('URL must start with http'); return }
    setSaving(true)
    setError('')
    try {
      await scrapedUrlsApi.add({
        tenant_id: tenantId,
        url: trimmed,
        source_id: sourceId ? parseInt(sourceId) : null,
      })
      onAdded()
      onClose()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to add URL')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#fff', borderRadius: 10, width: 480,
        boxShadow: '0 16px 48px rgba(0,0,0,0.2)', padding: 24,
      }}>
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Mark URL as Seen</div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, color: '#555', display: 'block', marginBottom: 4 }}>URL *</label>
          <input
            autoFocus
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            style={{
              width: '100%', padding: '8px 10px', border: '1px solid #d1d5db',
              borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
            }}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: '#555', display: 'block', marginBottom: 4 }}>Source (optional)</label>
          <select
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            style={{
              width: '100%', padding: '8px 10px', border: '1px solid #d1d5db',
              borderRadius: 6, fontSize: 13, background: '#fff',
            }}
          >
            <option value="">— No source / manual —</option>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            border: '1px solid #d1d5db', borderRadius: 6, background: '#fff',
            padding: '7px 16px', cursor: 'pointer', fontSize: 13,
          }}>Cancel</button>
          <button onClick={handleSave} disabled={saving || !url.trim()} style={{
            border: 'none', borderRadius: 6, background: '#1d4ed8', color: '#fff',
            padding: '7px 16px', cursor: saving || !url.trim() ? 'not-allowed' : 'pointer',
            fontSize: 13, opacity: !url.trim() ? 0.5 : 1,
          }}>{saving ? 'Adding…' : 'Add URL'}</button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ScrapedUrlsPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const tenantId = activeTenant?.id

  const [page, setPage] = useState(1)
  const [sourceFilter, setSourceFilter] = useState<number | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('')
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [sortBy, setSortBy] = useState<SortBy>('scraped_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [showAdd, setShowAdd] = useState(false)

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['scraped-urls', tenantId] })
  }, [qc, tenantId])

  const handleSearch = useCallback((value: string) => {
    setQ(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(value)
      setPage(1)
      setSelected(new Set())
    }, 300)
  }, [])

  const handleSort = useCallback((col: SortBy) => {
    setSortBy((prev) => {
      if (prev === col) {
        setSortDir((d) => d === 'asc' ? 'desc' : 'asc')
        return prev
      }
      setSortDir('desc')
      return col
    })
    setPage(1)
    setSelected(new Set())
  }, [])

  const { data, isFetching } = useQuery({
    queryKey: ['scraped-urls', tenantId, sourceFilter, page, debouncedQ, sortBy, sortDir, statusFilter],
    queryFn: () =>
      tenantId
        ? scrapedUrlsApi.list({
            tenant_id: tenantId, source_id: sourceFilter, q: debouncedQ,
            page, size: PAGE_SIZE, sort_by: sortBy, sort_dir: sortDir,
            status_filter: statusFilter || undefined,
          })
        : null,
    enabled: !!tenantId,
    placeholderData: (prev) => prev,
  })

  const { data: sources } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => (tenantId ? sourceApi.list(tenantId) : null),
    enabled: !!tenantId,
  })

  const deleteMut = useMutation({
    mutationFn: ({ id, deleteArticle }: { id: number; deleteArticle: boolean }) =>
      scrapedUrlsApi.delete(id, tenantId!, deleteArticle),
    onSuccess: () => { invalidate(); setSelected((s) => { s.delete(deleteMut.variables!.id); return new Set(s) }) },
  })

  const handleRemove = useCallback((row: { id: number; article_id: number | null; article_archived: boolean | null; article_enriched: boolean | null }) => {
    if (row.article_id) {
      const where = row.article_archived ? 'archive' : row.article_enriched ? 'news queue' : 'pending enrichment'
      const choice = window.confirm(
        `This article is still in your ${where}.\n\n` +
        `• OK  → Remove URL entry AND delete the article (allows fresh re-scrape)\n` +
        `• Cancel → Remove URL entry only (article stays; scraper will still skip it as a duplicate)`
      )
      deleteMut.mutate({ id: row.id, deleteArticle: choice })
    } else {
      deleteMut.mutate({ id: row.id, deleteArticle: false })
    }
  }, [deleteMut])

  const bulkDeleteMut = useMutation({
    mutationFn: (ids: number[]) => scrapedUrlsApi.bulkDelete(ids, tenantId!, true),
    onSuccess: (res) => {
      invalidate()
      setSelected(new Set())
      if (res.articles_deleted > 0) {
        alert(`Removed ${res.deleted} URL entries and ${res.articles_deleted} article${res.articles_deleted !== 1 ? 's' : ''}. These URLs can now be re-scraped.`)
      }
    },
  })

  const [clearing, setClearing] = useState(false)
  const handleClearAll = async () => {
    const count = data?.total ?? 0
    const label = sourceFilter
      ? `${sources?.find((s) => s.id === sourceFilter)?.name ?? 'this source'}`
      : 'ALL sources'
    if (!confirm(`Delete all ${count.toLocaleString()} seen URL${count !== 1 ? 's' : ''} for ${label}?\n\nThis cannot be undone.`)) return
    setClearing(true)
    try {
      const res = await scrapedUrlsApi.clear(tenantId!, sourceFilter)
      invalidate()
      setSelected(new Set())
      alert(`Deleted ${res.deleted.toLocaleString()} entries.`)
    } finally {
      setClearing(false)
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1
  const pageItems = data?.items ?? []
  const allPageSelected = pageItems.length > 0 && pageItems.every((r) => selected.has(r.id))

  const toggleAll = () => {
    if (allPageSelected) {
      setSelected((s) => { const next = new Set(s); pageItems.forEach((r) => next.delete(r.id)); return next })
    } else {
      setSelected((s) => { const next = new Set(s); pageItems.forEach((r) => next.add(r.id)); return next })
    }
  }

  const toggleRow = (id: number) => {
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  // Sortable column header
  const SortTh = ({ col, label, style: extraStyle }: { col: SortBy; label: string; style?: React.CSSProperties }) => {
    const active = sortBy === col
    return (
      <th
        onClick={() => handleSort(col)}
        style={{
          padding: '10px 14px', textAlign: 'left', fontSize: 11,
          fontWeight: 600, color: active ? '#374151' : '#888',
          textTransform: 'uppercase', letterSpacing: '0.5px',
          borderBottom: '1px solid #eee', cursor: 'pointer',
          userSelect: 'none', whiteSpace: 'nowrap',
          ...extraStyle,
        }}
      >
        {label}{' '}
        <span style={{ fontSize: 10, color: active ? '#374151' : '#d1d5db' }}>
          {active ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
        </span>
      </th>
    )
  }

  if (!tenantId) return <div style={{ padding: 32, color: '#aaa' }}>No tenant selected.</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 120px)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Seen URLs</h1>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: '#888' }}>
            Deduplication list — URLs here will be skipped by the scraper
          </p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {selected.size > 0 && (
            <button
              onClick={() => {
                if (!confirm(
                  `Remove ${selected.size} selected URL entr${selected.size !== 1 ? 'ies' : 'y'} and their associated articles?\n\n` +
                  `This allows those URLs to be scraped fresh on the next run.`
                )) return
                bulkDeleteMut.mutate([...selected])
              }}
              disabled={bulkDeleteMut.isPending}
              style={{
                padding: '7px 14px', border: '1px solid #fca5a5', borderRadius: 6,
                background: '#fff', color: '#dc2626', cursor: 'pointer', fontSize: 13, fontWeight: 500,
              }}
            >
              {bulkDeleteMut.isPending ? 'Deleting…' : `Delete ${selected.size} selected`}
            </button>
          )}
          <button
            onClick={() => setShowAdd(true)}
            style={{
              padding: '7px 14px', border: '1px solid #d1d5db', borderRadius: 6,
              background: '#fff', cursor: 'pointer', fontSize: 13,
            }}
          >
            + Add URL
          </button>
          <button
            onClick={handleClearAll}
            disabled={clearing || !data?.total}
            style={{
              padding: '7px 14px', border: '1px solid #fca5a5', borderRadius: 6,
              background: '#fff', color: '#dc2626', cursor: clearing || !data?.total ? 'not-allowed' : 'pointer',
              fontSize: 13, opacity: !data?.total ? 0.4 : 1,
            }}
          >
            {clearing ? 'Clearing…' : 'Clear All'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
        <select
          value={sourceFilter ?? ''}
          onChange={(e) => { setSourceFilter(e.target.value ? parseInt(e.target.value) : undefined); setPage(1); setSelected(new Set()) }}
          style={{
            padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6,
            fontSize: 13, background: '#fff', minWidth: 160,
          }}
        >
          <option value="">All Sources</option>
          {sources?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setPage(1); setSelected(new Set()) }}
          style={{
            padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6,
            fontSize: 13, background: '#fff', minWidth: 140,
          }}
        >
          <option value="">All Statuses</option>
          <option value="none">— No article</option>
          <option value="pending">Pending enrichment</option>
          <option value="queue">In queue</option>
          <option value="archived">Archived</option>
        </select>
        <input
          type="text"
          placeholder="Search URLs…"
          value={q}
          onChange={(e) => handleSearch(e.target.value)}
          style={{
            flex: 1, padding: '7px 12px', border: '1px solid #d1d5db',
            borderRadius: 6, fontSize: 13, outline: 'none',
          }}
        />
        <span style={{ fontSize: 12, color: '#9ca3af', alignSelf: 'center', whiteSpace: 'nowrap' }}>
          {data ? `${data.total.toLocaleString()} entries` : '—'}
          {isFetching && ' · Loading…'}
        </span>
      </div>

      {/* Table */}
      <div style={{
        flex: 1, minHeight: 0, overflowY: 'auto',
        border: '1px solid #e5e7eb', borderRadius: 10, background: '#fff',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8f9fa', position: 'sticky', top: 0, zIndex: 1 }}>
              <th style={{ width: 40, padding: '10px 14px', borderBottom: '1px solid #eee' }}>
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  onChange={toggleAll}
                  style={{ cursor: 'pointer' }}
                />
              </th>
              <th style={{
                padding: '10px 14px', textAlign: 'left', fontSize: 11,
                fontWeight: 600, color: '#888', textTransform: 'uppercase',
                letterSpacing: '0.5px', borderBottom: '1px solid #eee',
              }}>URL</th>
              <SortTh col="source" label="Source" />
              <SortTh col="status" label="Status" />
              <SortTh col="scraped_at" label="Seen" />
              <th style={{ padding: '10px 14px', borderBottom: '1px solid #eee' }} />
            </tr>
          </thead>
          <tbody>
            {pageItems.length === 0 && !isFetching && (
              <tr>
                <td colSpan={6} style={{ padding: 48, textAlign: 'center', color: '#bbb', fontSize: 13 }}>
                  {debouncedQ || sourceFilter || statusFilter ? 'No entries match your filters.' : 'No seen URLs recorded yet.'}
                </td>
              </tr>
            )}
            {pageItems.map((row) => (
              <tr
                key={row.id}
                style={{ borderBottom: '1px solid #f5f5f5', background: selected.has(row.id) ? '#eff6ff' : undefined }}
                onMouseEnter={(e) => { if (!selected.has(row.id)) e.currentTarget.style.background = '#fafafa' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = selected.has(row.id) ? '#eff6ff' : '' }}
              >
                <td style={{ padding: '8px 14px' }}>
                  <input
                    type="checkbox"
                    checked={selected.has(row.id)}
                    onChange={() => toggleRow(row.id)}
                    style={{ cursor: 'pointer' }}
                  />
                </td>
                <td style={{ padding: '8px 14px', maxWidth: 500 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{
                      fontSize: 12, color: '#374151', fontFamily: 'monospace',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      display: 'block', maxWidth: 520,
                    }} title={row.url}>
                      {row.url}
                    </span>
                    <a
                      href={row.url} target="_blank" rel="noopener"
                      style={{ color: '#9ca3af', flexShrink: 0, textDecoration: 'none', fontSize: 12 }}
                      title="Open in new tab"
                    >↗</a>
                  </div>
                </td>
                <td style={{ padding: '8px 14px' }}>
                  {row.source_name ? (
                    <span style={{
                      display: 'inline-block', background: '#f0f4ff', color: '#3b5bdb',
                      fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 500,
                      maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }} title={row.source_name}>
                      {row.source_name}
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, color: '#d1d5db' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '8px 14px' }}>
                  {row.article_id ? (
                    row.article_archived ? (
                      <Link
                        to="/archive"
                        style={{
                          display: 'inline-block', fontSize: 10, fontWeight: 600,
                          padding: '2px 7px', borderRadius: 10, textDecoration: 'none',
                          background: '#f3f4f6', color: '#6b7280',
                        }}
                        title="Article is archived — click to open archive"
                      >
                        Archived
                      </Link>
                    ) : row.article_enriched ? (
                      <button
                        onClick={() => navigate(`/articles?highlight=${row.article_id}`)}
                        style={{
                          display: 'inline-block', fontSize: 10, fontWeight: 600,
                          padding: '2px 7px', borderRadius: 10, border: 'none', cursor: 'pointer',
                          background: '#fef9c3', color: '#854d0e',
                        }}
                        title="Article is in the news queue — click to jump to it"
                      >
                        In queue
                      </button>
                    ) : (
                      <span
                        style={{
                          display: 'inline-block', fontSize: 10, fontWeight: 600,
                          padding: '2px 7px', borderRadius: 10,
                          background: '#eff6ff', color: '#3b82f6',
                        }}
                        title="Scraped but awaiting AI enrichment"
                      >
                        Pending
                      </span>
                    )
                  ) : (
                    <span style={{ fontSize: 10, color: '#d1d5db' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '8px 14px', fontSize: 11, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                  {row.scraped_at ? formatDistanceToNow(parseISO(row.scraped_at), { addSuffix: true }) : '—'}
                </td>
                <td style={{ padding: '8px 14px', textAlign: 'right' }}>
                  <button
                    onClick={() => handleRemove(row)}
                    disabled={deleteMut.isPending && deleteMut.variables?.id === row.id}
                    style={{
                      border: '1px solid #fca5a5', borderRadius: 4, background: '#fff',
                      color: '#dc2626', cursor: 'pointer', fontSize: 11, padding: '3px 8px',
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
        fontSize: 12, color: '#6b7280',
      }}>
        <button
          onClick={() => { setPage((p) => Math.max(1, p - 1)); setSelected(new Set()) }}
          disabled={page <= 1}
          style={{
            border: '1px solid #d1d5db', borderRadius: 4, background: '#fff',
            padding: '4px 12px', cursor: page <= 1 ? 'not-allowed' : 'pointer',
            color: page <= 1 ? '#d1d5db' : '#374151', fontSize: 12,
          }}
        >← Prev</button>
        <span>Page {page} of {totalPages || 1}</span>
        <button
          onClick={() => { setPage((p) => Math.min(totalPages, p + 1)); setSelected(new Set()) }}
          disabled={page >= totalPages}
          style={{
            border: '1px solid #d1d5db', borderRadius: 4, background: '#fff',
            padding: '4px 12px', cursor: page >= totalPages ? 'not-allowed' : 'pointer',
            color: page >= totalPages ? '#d1d5db' : '#374151', fontSize: 12,
          }}
        >Next →</button>
        {data && (
          <span style={{ marginLeft: 4 }}>
            Showing {Math.min((page - 1) * PAGE_SIZE + 1, data.total).toLocaleString()}–{Math.min(page * PAGE_SIZE, data.total).toLocaleString()} of {data.total.toLocaleString()}
          </span>
        )}
      </div>

      {showAdd && sources && (
        <AddUrlModal
          tenantId={tenantId}
          sources={sources}
          onClose={() => setShowAdd(false)}
          onAdded={invalidate}
        />
      )}
    </div>
  )
}
