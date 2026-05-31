import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { catalogApi } from '@/api/catalog'
import { sourceApi } from '@/api/sources'
import type { CatalogSource } from '@/api/types'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Spinner from '@/components/ui/Spinner'

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
