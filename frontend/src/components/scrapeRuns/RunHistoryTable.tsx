import React, { useState } from 'react'
import { formatDistanceToNow, differenceInSeconds } from 'date-fns'
import type { ScrapeRun } from '@/api/types'
import Badge from '@/components/ui/Badge'

const statusVariant = (s: ScrapeRun['status']) =>
  s === 'success' ? 'success' : s === 'error' ? 'error' : s === 'running' ? 'info' : 'warning'

interface Props { runs: ScrapeRun[] }

export default function RunHistoryTable({ runs }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null)

  if (!runs.length) {
    return <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>No scrape runs yet.</div>
  }

  return (
    <div style={{ background: '#fff', borderRadius: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f8f9fa', borderBottom: '1px solid #eee' }}>
            {['Time', 'Duration', 'Found', 'New', 'Status', ''].map((h) => (
              <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const dur = r.completed_at
              ? differenceInSeconds(new Date(r.completed_at), new Date(r.started_at))
              : null
            return (
              <React.Fragment key={r.id}>
                <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '11px 14px', fontSize: 13 }}>
                    {formatDistanceToNow(new Date(r.started_at), { addSuffix: true })}
                  </td>
                  <td style={{ padding: '11px 14px', fontSize: 13, color: '#888' }}>
                    {dur !== null ? `${dur}s` : '—'}
                  </td>
                  <td style={{ padding: '11px 14px', fontWeight: 600 }}>{r.articles_found}</td>
                  <td style={{ padding: '11px 14px', fontWeight: 600, color: r.articles_new > 0 ? 'var(--brand-color)' : '#aaa' }}>{r.articles_new}</td>
                  <td style={{ padding: '11px 14px' }}>
                    <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                  </td>
                  <td style={{ padding: '11px 14px' }}>
                    {r.error_message && (
                      <button
                        onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                        style={{ fontSize: 12, color: '#e53935', background: 'none', border: 'none', cursor: 'pointer' }}
                      >
                        {expanded === r.id ? 'Hide' : 'View error'}
                      </button>
                    )}
                  </td>
                </tr>
                {expanded === r.id && r.error_message && (
                  <tr>
                    <td colSpan={6} style={{ padding: '0 14px 12px' }}>
                      <pre style={{ fontSize: 12, background: '#ffebee', color: '#c62828', padding: 10, borderRadius: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {r.error_message}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
