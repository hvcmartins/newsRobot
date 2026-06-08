import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sourceApi } from '@/api/sources'
import type { Source } from '@/api/types'
import { formatDistanceToNow, parseISO } from 'date-fns'

const PAGE_SIZE = 50

interface Props {
  source: Source
  onClose: () => void
}

export default function ScrapedUrlsModal({ source, onClose }: Props) {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const [clearing, setClearing] = useState(false)

  const handleSearch = useCallback((value: string) => {
    setQ(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(value)
      setPage(1)
    }, 300)
  }, [])

  const { data, isFetching } = useQuery({
    queryKey: ['scraped-urls', source.id, page, debouncedQ],
    queryFn: () => sourceApi.listScrapedUrls(source.id, page, PAGE_SIZE, debouncedQ),
    placeholderData: (prev) => prev,
  })

  const deleteMut = useMutation({
    mutationFn: (urlId: number) => sourceApi.deleteScrapedUrl(source.id, urlId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scraped-urls', source.id] }),
  })

  const handleClearAll = async () => {
    if (!confirm(`Clear ALL ${data?.total ?? ''} seen URLs for "${source.name}"?\n\nThe next scrape will re-evaluate every article from this source.`)) return
    setClearing(true)
    try {
      const result = await sourceApi.clearScrapedUrls(source.id)
      qc.invalidateQueries({ queryKey: ['scraped-urls', source.id] })
      setPage(1)
      alert(`Cleared ${result.cleared} entries.`)
    } finally {
      setClearing(false)
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: 24,
    }} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#fff', borderRadius: 12, width: '100%', maxWidth: 860,
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px', borderBottom: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>Seen URLs</div>
            <div style={{ fontSize: 12, color: '#888', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {source.name}
              {data && <span style={{ color: '#aaa' }}> · {data.total.toLocaleString()} entries</span>}
            </div>
          </div>
          <button onClick={onClose} style={{
            border: 'none', background: 'none', cursor: 'pointer',
            fontSize: 20, color: '#aaa', lineHeight: 1, padding: 4,
          }}>×</button>
        </div>

        {/* Search */}
        <div style={{ padding: '12px 24px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
          <input
            type="text"
            placeholder="Search URLs…"
            value={q}
            onChange={(e) => handleSearch(e.target.value)}
            style={{
              width: '100%', padding: '8px 12px', border: '1px solid #d1d5db',
              borderRadius: 6, fontSize: 13, outline: 'none', boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {isFetching && !data && (
            <div style={{ padding: 32, textAlign: 'center', color: '#aaa', fontSize: 13 }}>Loading…</div>
          )}
          {data && data.items.length === 0 && (
            <div style={{ padding: 48, textAlign: 'center', color: '#bbb', fontSize: 13 }}>
              {debouncedQ ? 'No URLs match your search.' : 'No seen URLs recorded yet.'}
            </div>
          )}
          {data && data.items.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8f9fa', position: 'sticky', top: 0 }}>
                  {['URL', 'Seen', ''].map((h) => (
                    <th key={h} style={{
                      padding: '9px 16px', textAlign: 'left', fontSize: 11,
                      fontWeight: 600, color: '#888', textTransform: 'uppercase',
                      letterSpacing: '0.5px', borderBottom: '1px solid #eee',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => (
                  <tr key={entry.id} style={{ borderBottom: '1px solid #f5f5f5' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#fafafa')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                    <td style={{ padding: '8px 16px', maxWidth: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{
                          fontSize: 12, color: '#374151', fontFamily: 'monospace',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          display: 'block', maxWidth: 480,
                        }} title={entry.url}>
                          {entry.url}
                        </span>
                        <a href={entry.url} target="_blank" rel="noopener"
                          style={{ color: '#9ca3af', flexShrink: 0, lineHeight: 1, textDecoration: 'none', fontSize: 12 }}
                          title="Open in new tab">
                          ↗
                        </a>
                      </div>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 11, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                      {entry.scraped_at
                        ? formatDistanceToNow(parseISO(entry.scraped_at), { addSuffix: true })
                        : '—'}
                    </td>
                    <td style={{ padding: '8px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => deleteMut.mutate(entry.id)}
                        disabled={deleteMut.isPending}
                        title="Remove so this URL can be re-scraped"
                        style={{
                          border: '1px solid #fca5a5', borderRadius: 4, background: '#fff',
                          color: '#dc2626', cursor: 'pointer', fontSize: 11,
                          padding: '3px 8px', lineHeight: 1.4,
                        }}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 24px', borderTop: '1px solid #e5e7eb', flexShrink: 0,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          {/* Pagination */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{
                border: '1px solid #d1d5db', borderRadius: 4, background: '#fff',
                padding: '4px 10px', cursor: page <= 1 ? 'not-allowed' : 'pointer',
                color: page <= 1 ? '#ccc' : '#374151', fontSize: 12,
              }}
            >← Prev</button>
            <span style={{ fontSize: 12, color: '#6b7280' }}>
              Page {page} of {totalPages || 1}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{
                border: '1px solid #d1d5db', borderRadius: 4, background: '#fff',
                padding: '4px 10px', cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                color: page >= totalPages ? '#ccc' : '#374151', fontSize: 12,
              }}
            >Next →</button>
            {isFetching && <span style={{ fontSize: 11, color: '#aaa' }}>Loading…</span>}
          </div>

          <button
            onClick={handleClearAll}
            disabled={clearing || !data?.total}
            style={{
              border: '1px solid #fca5a5', borderRadius: 6, background: '#fff',
              color: '#dc2626', cursor: clearing || !data?.total ? 'not-allowed' : 'pointer',
              fontSize: 12, padding: '6px 14px', opacity: !data?.total ? 0.4 : 1,
            }}
          >
            {clearing ? 'Clearing…' : '↺ Clear All'}
          </button>

          <button
            onClick={onClose}
            style={{
              border: '1px solid #d1d5db', borderRadius: 6, background: '#fff',
              color: '#374151', cursor: 'pointer', fontSize: 12, padding: '6px 14px',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
