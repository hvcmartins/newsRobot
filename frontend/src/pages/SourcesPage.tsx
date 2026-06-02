import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTenant } from '@/contexts/TenantContext'
import { sourceApi, type SourceCheckResult } from '@/api/sources'
import { catalogApi, type DiscoveredSource } from '@/api/catalog'
import SourceList from '@/components/sources/SourceList'
import SourceForm from '@/components/sources/SourceForm'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Spinner from '@/components/ui/Spinner'

function AIDiscoverDrawer({ tenantId, onClose }: { tenantId: number; onClose: () => void }) {
  const qc = useQueryClient()
  const [results, setResults] = useState<DiscoveredSource[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [addingUrl, setAddingUrl] = useState<string | null>(null)
  const [addedUrls, setAddedUrls] = useState<Set<string>>(new Set())

  const discoverMut = useMutation({
    mutationFn: () => catalogApi.discover(tenantId),
    onSuccess: (data) => { setResults(data.sources); setError(null) },
    onError: (e: unknown) => { setError(e instanceof Error ? e.message : 'Discovery failed'); setResults(null) },
  })

  React.useEffect(() => { discoverMut.mutate() }, [])  // auto-run on open

  const handleAdd = async (src: DiscoveredSource) => {
    setAddingUrl(src.url)
    try {
      await catalogApi.addDiscovered(tenantId, {
        name: src.name, url: src.url, type: src.type,
        category: src.category, description: src.description,
      })
      setAddedUrls((prev) => new Set([...prev, src.url]))
      qc.invalidateQueries({ queryKey: ['sources', tenantId] })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setAddingUrl(null)
    }
  }

  return (
    <div style={{
      background: 'linear-gradient(135deg, #f0f7ff 0%, #fafbff 100%)',
      border: '1px solid #c7ddf8', borderRadius: 12, padding: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 15 }}>🔍 AI Source Discovery</span>
          <p style={{ fontSize: 12, color: '#5a7fa8', marginTop: 2 }}>
            Searching for sources that match your AI Topic Profile…
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {!discoverMut.isPending && (
            <Button variant="secondary" size="sm" onClick={() => { setResults(null); setError(null); discoverMut.mutate() }}>
              Retry
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={onClose}>✕ Close</Button>
        </div>
      </div>

      {discoverMut.isPending && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#5a7fa8', fontSize: 13, padding: '16px 0' }}>
          <Spinner size={20} />
          <span>AI is analysing your profile and searching for sources…</span>
        </div>
      )}

      {error && (
        <div style={{ background: '#fff1f0', border: '1px solid #ffa39e', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#cf1322' }}>
          {error}
        </div>
      )}

      {results && results.length === 0 && (
        <p style={{ fontSize: 13, color: '#888' }}>No new sources found. Try expanding your AI Topic Profile.</p>
      )}

      {results && results.length > 0 && (
        <>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
            Found <strong>{results.filter(s => s.reachable).length} live</strong> / {results.length} suggested sources.
            {' '}<span style={{ color: '#aaa' }}>AI suggestions may include invented URLs — "Offline" sources could not be reached.</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {results.map((src) => {
              const isAdded = addedUrls.has(src.url) || src.already_in_feed
              return (
                <div key={src.url} style={{
                  background: src.reachable ? '#fff' : '#fafafa', borderRadius: 8, padding: '12px 14px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  border: isAdded ? '1.5px solid var(--brand-color)' : src.reachable ? '1.5px solid #e8edf5' : '1.5px solid #eee',
                  display: 'flex', alignItems: 'flex-start', gap: 12,
                  opacity: src.reachable ? 1 : 0.6,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{src.name}</span>
                      <Badge variant="neutral">{src.category}</Badge>
                      <Badge variant="neutral">{src.type.toUpperCase()}</Badge>
                      {src.reachable
                        ? <Badge variant="success">● Live</Badge>
                        : <Badge variant="neutral">○ Offline</Badge>}
                      {src.url_corrected && <Badge variant="info">URL corrected</Badge>}
                      {src.in_catalog && <Badge variant="info">In catalog</Badge>}
                    </div>
                    {src.description && (
                      <p style={{ fontSize: 12, color: '#666', margin: '4px 0 2px', lineHeight: 1.4 }}>{src.description}</p>
                    )}
                    {src.reason && (
                      <p style={{ fontSize: 11, color: '#999', fontStyle: 'italic', margin: 0 }}>{src.reason}</p>
                    )}
                    <a href={src.url} target="_blank" rel="noreferrer"
                      style={{ fontSize: 11, color: '#1677ff', textDecoration: 'none', display: 'block', marginTop: 3, wordBreak: 'break-all' }}>
                      {src.url}
                    </a>
                  </div>
                  <Button
                    size="sm"
                    variant={isAdded ? 'secondary' : 'primary'}
                    disabled={isAdded || addingUrl === src.url}
                    loading={addingUrl === src.url}
                    onClick={() => handleAdd(src)}
                    style={{ flexShrink: 0 }}
                  >
                    {isAdded ? '✓ Added' : '+ Add'}
                  </Button>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

export default function SourcesPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [showDiscover, setShowDiscover] = useState(false)
  const [checkResults, setCheckResults] = useState<Map<number, SourceCheckResult> | null>(null)
  const [checkingAll, setCheckingAll] = useState(false)
  const tenantId = activeTenant?.id ?? 0

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const createMut = useMutation({
    mutationFn: sourceApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', tenantId] }),
  })

  const handleCheckAll = async () => {
    setCheckingAll(true)
    setCheckResults(new Map())
    try {
      const data = await sourceApi.checkAll(tenantId)
      const map = new Map<number, SourceCheckResult>()
      data.results.forEach(r => map.set(r.id, r))
      setCheckResults(map)
    } catch {
      setCheckResults(null)
    } finally {
      setCheckingAll(false)
    }
  }

  if (!activeTenant) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>My Sources</h1>
          <p style={{ fontSize: 13, color: '#888', marginTop: 2 }}>{sources.length} source{sources.length !== 1 ? 's' : ''} configured</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button
            variant="secondary"
            size="sm"
            loading={checkingAll}
            onClick={handleCheckAll}
            disabled={!tenantId || sources.length === 0}
          >
            {checkResults && !checkingAll ? '↺ Re-check' : '⚡ Check all'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowDiscover((v) => !v)}
          >
            🔍 AI Discover
          </Button>
          <Link to="/source-library">
            <Button variant="secondary" size="sm">📚 Browse Library</Button>
          </Link>
          <Button size="sm" onClick={() => setShowAdd(true)}>+ Add Custom Source</Button>
        </div>
      </div>

      {showDiscover && tenantId > 0 && (
        <AIDiscoverDrawer tenantId={tenantId} onClose={() => setShowDiscover(false)} />
      )}

      {isLoading ? (
        <p style={{ color: '#999' }}>Loading…</p>
      ) : (
        <SourceList
          sources={sources}
          tenantId={tenantId}
          checkResults={checkResults ?? undefined}
          checkingAll={checkingAll}
        />
      )}

      {showAdd && (
        <SourceForm
          initial={{ tenant_id: tenantId }}
          onSave={async (data) => { await createMut.mutateAsync(data) }}
          onClose={() => setShowAdd(false)}
        />
      )}
    </div>
  )
}
