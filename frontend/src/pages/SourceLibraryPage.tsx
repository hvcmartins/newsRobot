import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { catalogApi, type DiscoveredSource } from '@/api/catalog'
import { sourceApi } from '@/api/sources'
import type { CatalogSource } from '@/api/types'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Spinner from '@/components/ui/Spinner'

function DiscoverPanel({ tenantId }: { tenantId: number }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<DiscoveredSource[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [addingUrl, setAddingUrl] = useState<string | null>(null)
  const [addedUrls, setAddedUrls] = useState<Set<string>>(new Set())

  const discoverMutation = useMutation({
    mutationFn: () => catalogApi.discover(tenantId),
    onSuccess: (data) => {
      setResults(data.sources)
      setError(null)
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : 'Discovery failed')
      setResults(null)
    },
  })

  const handleDiscover = () => {
    setOpen(true)
    setResults(null)
    setError(null)
    discoverMutation.mutate()
  }

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

  if (!tenantId) return null

  return (
    <div style={{
      background: 'linear-gradient(135deg, #f0f7ff 0%, #fafbff 100%)',
      border: '1px solid #c7ddf8', borderRadius: 12, padding: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>🔍</span>
            <span style={{ fontWeight: 700, fontSize: 15 }}>Discover Sources with AI</span>
          </div>
          <p style={{ fontSize: 12, color: '#5a7fa8', marginTop: 4 }}>
            Based on your AI Topic Profile, the AI searches for reliable RSS feeds and news sources that match your interests.
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          loading={discoverMutation.isPending}
          onClick={handleDiscover}
          disabled={discoverMutation.isPending}
        >
          {discoverMutation.isPending ? 'Discovering…' : open ? 'Rediscover' : 'Discover'}
        </Button>
      </div>

      {open && (
        <div style={{ marginTop: 16 }}>
          {discoverMutation.isPending && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#5a7fa8', fontSize: 13 }}>
              <Spinner size={18} />
              <span>AI is searching for sources matching your profile…</span>
            </div>
          )}

          {error && (
            <div style={{ background: '#fff1f0', border: '1px solid #ffa39e', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#cf1322' }}>
              {error}
            </div>
          )}

          {results && results.length === 0 && (
            <p style={{ fontSize: 13, color: '#888' }}>No new sources suggested. Try updating your AI Topic Profile.</p>
          )}

          {results && results.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginTop: 8 }}>
              {results.map((src) => {
                const isAdded = addedUrls.has(src.url) || src.already_in_feed
                return (
                  <div key={src.url} style={{
                    background: '#fff', borderRadius: 10, padding: 14,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                    border: isAdded ? '2px solid var(--brand-color)' : '2px solid transparent',
                    display: 'flex', flexDirection: 'column', gap: 8,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{src.name}</div>
                      <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                        {src.reachable
                          ? <Badge variant="success">● Live</Badge>
                          : <Badge variant="neutral">○ Offline</Badge>}
                        {src.in_catalog && <Badge variant="info">In catalog</Badge>}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      <Badge variant="neutral">{src.category}</Badge>
                      <Badge variant="neutral">{src.type.toUpperCase()}</Badge>
                    </div>

                    {src.description && (
                      <p style={{ fontSize: 12, color: '#666', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                        {src.description}
                      </p>
                    )}

                    {src.reason && (
                      <p style={{ fontSize: 11, color: '#888', fontStyle: 'italic', lineHeight: 1.4 }}>
                        {src.reason}
                      </p>
                    )}

                    <a href={src.url} target="_blank" rel="noreferrer"
                      style={{ fontSize: 11, color: '#1677ff', wordBreak: 'break-all', textDecoration: 'none' }}>
                      {src.url}
                    </a>

                    <Button
                      size="sm"
                      variant={isAdded ? 'secondary' : 'primary'}
                      disabled={isAdded || addingUrl === src.url}
                      loading={addingUrl === src.url}
                      onClick={() => handleAdd(src)}
                      style={{ marginTop: 'auto' }}
                    >
                      {isAdded ? '✓ Added' : '+ Add to Feed'}
                    </Button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SourceLibraryPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [category, setCategory] = useState('')
  const [language, setLanguage] = useState('')
  const [q, setQ] = useState('')
  const [adding, setAdding] = useState<number | null>(null)
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set())

  const tenantId = activeTenant?.id ?? 0

  const { data: categories = [] } = useQuery({
    queryKey: ['catalog-categories'],
    queryFn: catalogApi.categories,
  })

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['catalog', { category, language, q }],
    queryFn: () => catalogApi.list({ category: category || undefined, language: language || undefined, q: q || undefined }),
  })

  const { data: tenantSources = [] } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const addedCatalogIds = new Set(
    tenantSources.map((s) => s.catalog_source_id).filter(Boolean)
  )
  const allAdded = new Set([...addedCatalogIds, ...addedIds])

  const handleAdd = async (cs: CatalogSource) => {
    if (!tenantId) return
    setAdding(cs.id)
    try {
      await catalogApi.addToTenant(cs.id, tenantId)
      setAddedIds((prev) => new Set([...prev, cs.id]))
      qc.invalidateQueries({ queryKey: ['sources', tenantId] })
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setAdding(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Source Library</h1>
        <p style={{ fontSize: 13, color: '#888', marginTop: 2 }}>Curated reliable news sources — click "Add to Feed" to start receiving articles.</p>
      </div>

      <DiscoverPanel tenantId={tenantId} />

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input
          placeholder="Search sources..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, minWidth: 200, background: '#fff' }}
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, background: '#fff' }}
        >
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, background: '#fff' }}
        >
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="pt">Portuguese</option>
          <option value="es">Spanish</option>
          <option value="de">German</option>
          <option value="fr">French</option>
        </select>
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner size={36} /></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
          {sources.map((cs: CatalogSource) => (
            <div key={cs.id} style={{
              background: '#fff', borderRadius: 10, padding: 16,
              boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
              display: 'flex', flexDirection: 'column', gap: 10,
              border: allAdded.has(cs.id) ? '2px solid var(--brand-color)' : '2px solid transparent',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                {cs.logo_url ? (
                  <img src={cs.logo_url} alt="" style={{ width: 36, height: 36, objectFit: 'contain', borderRadius: 4, flexShrink: 0 }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                ) : (
                  <div style={{ width: 36, height: 36, background: 'var(--brand-color-light)', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>📰</div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{cs.name}</div>
                  <div style={{ display: 'flex', gap: 5, marginTop: 4, flexWrap: 'wrap' }}>
                    <Badge variant="neutral">{cs.category}</Badge>
                    <Badge variant="info">{cs.language.toUpperCase()}</Badge>
                    {cs.country && <Badge variant="neutral">{cs.country}</Badge>}
                    {cs.is_verified && <Badge variant="success">✓ Verified</Badge>}
                  </div>
                </div>
              </div>

              {cs.description && (
                <p style={{ fontSize: 12, color: '#666', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                  {cs.description}
                </p>
              )}

              <Button
                size="sm"
                variant={allAdded.has(cs.id) ? 'secondary' : 'primary'}
                disabled={allAdded.has(cs.id) || !tenantId}
                loading={adding === cs.id}
                onClick={() => handleAdd(cs)}
                style={{ marginTop: 'auto' }}
              >
                {allAdded.has(cs.id) ? '✓ Added' : '+ Add to Feed'}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
