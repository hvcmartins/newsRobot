import React, { useState } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { sourceApi } from '@/api/sources'
import type { Source } from '@/api/types'
import type { SourceCheckResult } from '@/api/sources'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import SourceForm from './SourceForm'
import SourceTestResult from './SourceTestResult'
import { formatDistanceToNow } from 'date-fns'

interface Props {
  sources: Source[]
  tenantId: number
  checkResults?: Map<number, SourceCheckResult>
  checkingAll?: boolean
}

export default function SourceList({ sources, tenantId, checkResults, checkingAll }: Props) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Source | null>(null)
  const [testResult, setTestResult] = useState<{ id: number; data: unknown } | null>(null)
  const [testing, setTesting] = useState<number | null>(null)

  const deleteMut = useMutation({
    mutationFn: sourceApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', tenantId] }),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      sourceApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', tenantId] }),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Source> }) =>
      sourceApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', tenantId] }),
  })

  const handleTest = async (id: number) => {
    setTesting(id)
    try {
      const result = await sourceApi.test(id)
      setTestResult({ id, data: result })
    } catch (e: unknown) {
      setTestResult({ id, data: { error: e instanceof Error ? e.message : 'Test failed' } })
    } finally {
      setTesting(null)
    }
  }

  if (!sources.length) {
    return (
      <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>
        <p>No sources yet. Add one above or browse the Source Library.</p>
      </div>
    )
  }

  return (
    <>
      <div style={{ background: '#fff', borderRadius: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8f9fa', borderBottom: '1px solid #eee' }}>
              {['Name', 'URL', 'Type', 'Last Scraped', 'Status', 'Actions'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '12px 14px', fontWeight: 500 }}>{s.name}</td>
                <td style={{ padding: '12px 14px', maxWidth: 200 }}>
                  <a href={s.url} target="_blank" rel="noopener" style={{ fontSize: 12, color: '#888', textOverflow: 'ellipsis', overflow: 'hidden', display: 'block', whiteSpace: 'nowrap' }}>{s.url}</a>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <Badge variant={s.type === 'rss' ? 'info' : 'neutral'}>{s.type.toUpperCase()}</Badge>
                </td>
                <td style={{ padding: '12px 14px', fontSize: 12, color: '#999' }}>
                  {s.last_scraped_at ? formatDistanceToNow(new Date(s.last_scraped_at), { addSuffix: true }) : 'Never'}
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <Badge variant={s.is_active ? 'success' : 'neutral'}>{s.is_active ? 'Active' : 'Paused'}</Badge>
                    {checkingAll && !checkResults?.has(s.id) && (
                      <span style={{ fontSize: 11, color: '#aaa' }}>checking…</span>
                    )}
                    {checkResults?.has(s.id) && (() => {
                      const r = checkResults.get(s.id)!
                      return r.online
                        ? <Badge variant="success">● Online{r.http_status ? ` ${r.http_status}` : ''}</Badge>
                        : <span title={r.error}><Badge variant="error">✕ Offline</Badge></span>
                    })()}
                  </div>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Button size="sm" variant="ghost"
                      onClick={() => toggleMut.mutate({ id: s.id, is_active: !s.is_active })}
                      style={{ color: '#555', border: '1px solid #ddd', padding: '4px 8px' }}>
                      {s.is_active ? 'Pause' : 'Resume'}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditing(s)}>Edit</Button>
                    <Button size="sm" variant="secondary" loading={testing === s.id} onClick={() => handleTest(s.id)}>Test</Button>
                    <Button size="sm" variant="danger"
                      onClick={() => {
                        if (confirm(`Delete "${s.name}"?`)) deleteMut.mutate(s.id)
                      }}>
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {testResult && testResult.id && (
        <SourceTestResult
          data={testResult.data}
          onClose={() => setTestResult(null)}
        />
      )}

      {editing && (
        <SourceForm
          initial={editing}
          onSave={async (data) => {
            await updateMut.mutateAsync({ id: editing.id, data })
          }}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}
