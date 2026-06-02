import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sourceApi } from '@/api/sources'
import { scrapeRunApi } from '@/api/scrapeRuns'
import ArticleFeed from '@/components/articles/ArticleFeed'
import ArticleFilters, { Filters } from '@/components/articles/ArticleFilters'
import Button from '@/components/ui/Button'

export default function ArticlesPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [filters, setFilters] = useState<Filters>({})
  const [page, setPage] = useState(1)

  const tenantId = activeTenant?.id ?? 0

  const { data: sources = [] } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['articles', tenantId, filters, page],
    queryFn: () => articleApi.list({ tenant_id: tenantId, ...filters, page, size: 20 }),
    enabled: !!tenantId,
  })

  const { data: enrichStatus } = useQuery({
    queryKey: ['enrichment-status', tenantId],
    queryFn: () => articleApi.enrichmentStatus(tenantId),
    enabled: !!tenantId,
    refetchInterval: (query) => (query.state.data?.pending ?? 0) > 0 ? 3000 : false,
  })

  const { data: dashboard } = useQuery({
    queryKey: ['dashboard', tenantId],
    queryFn: () => articleApi.dashboard(tenantId),
    enabled: !!tenantId,
    refetchInterval: 60_000,
  })

  const categories = React.useMemo(() => {
    const cats = new Set((data?.items ?? []).map((a) => a.category).filter(Boolean) as string[])
    return [...cats].sort()
  }, [data?.items])

  const markReadMut = useMutation({
    mutationFn: articleApi.markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const scrapeMut = useMutation({
    mutationFn: () => scrapeRunApi.triggerFull(tenantId),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['articles', tenantId] }), 3000)
    },
  })

  const [enrichError, setEnrichError] = useState<string | null>(null)
  const enrichMut = useMutation({
    mutationFn: () => articleApi.triggerEnrich(tenantId, false),
    onSuccess: (data) => {
      setEnrichError(null)
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
      if (data.queued === 0) setEnrichError('No pending articles found — use Re-enrich to reprocess all.')
    },
    onError: (err: Error) => setEnrichError(err.message),
  })
  const stopEnrichMut = useMutation({
    mutationFn: () => articleApi.stopEnrich(tenantId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] }),
  })
  const reEnrichMut = useMutation({
    mutationFn: () => articleApi.triggerEnrich(tenantId, true),
    onSuccess: () => {
      setEnrichError(null)
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
    },
    onError: (err: Error) => setEnrichError(err.message),
  })

  const reEnrichSingleMut = useMutation({
    mutationFn: (id: number) => articleApi.reEnrich(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
    },
  })

  const handleFilterChange = useCallback((f: Filters) => {
    setFilters(f)
    setPage(1)
  }, [])

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select or create a tenant to get started.</div>
  }

  const pending = enrichStatus?.pending ?? 0
  const enrichTotal = enrichStatus?.total ?? 0
  const enriched = enrichStatus?.enriched ?? 0
  const enrichPct = enrichTotal > 0 ? Math.round((enriched / enrichTotal) * 100) : 0
  const isPaused = enrichStatus?.paused ?? false
  const tps: number | null = enrichStatus?.tokens_per_second ?? null
  const secsPerArticle: number | null = enrichStatus?.seconds_per_article ?? null
  const etaSecs = secsPerArticle != null && pending > 0 ? Math.ceil(secsPerArticle * pending) : null
  const etaLabel = etaSecs == null ? null
    : etaSecs < 60 ? `~${etaSecs}s left`
    : `~${Math.ceil(etaSecs / 60)}min left`

  const nextSend = dashboard?.next_send_at
    ? formatDistanceToNow(new Date(dashboard.next_send_at), { addSuffix: true })
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>News Queue</h1>
          <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
            {data?.total != null
              ? `${data.total} article${data.total !== 1 ? 's' : ''} pending`
              : 'Pending articles awaiting your next digest'}
            {nextSend && (
              <span style={{ marginLeft: 8, color: 'var(--brand-color)', fontWeight: 500 }}>
                · Next send {nextSend}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="sm" loading={scrapeMut.isPending} onClick={() => scrapeMut.mutate()}>
            🔄 Scrape now
          </Button>
        </div>
      </div>

      {/* AI enrichment progress banner */}
      {(enrichTotal > 0 || enrichError) && (
        <div style={{
          background: pending === 0 ? '#e8f5e9' : isPaused ? '#f5f5f5' : '#f3e5f5',
          borderRadius: 8,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 13, flexShrink: 0,
            color: pending === 0 ? '#2e7d32' : isPaused ? '#757575' : '#7b1fa2' }}>
            {pending === 0
              ? `✦ AI enrichment complete — ${enrichTotal} articles`
              : isPaused
              ? `⏸ Enrichment paused — ${enriched} / ${enrichTotal} (${enrichPct}%)`
              : `✦ AI enriching… ${enriched} / ${enrichTotal} articles (${enrichPct}%)`}
          </span>
          <div style={{
            flex: 1, minWidth: 80, height: 6, borderRadius: 3,
            background: pending === 0 ? '#c8e6c9' : isPaused ? '#e0e0e0' : '#e1bee7',
          }}>
            <div style={{
              width: `${enrichPct}%`, height: '100%', borderRadius: 3,
              background: pending === 0 ? '#4caf50' : isPaused ? '#9e9e9e' : '#9c27b0',
              transition: 'width 0.6s ease',
            }} />
          </div>
          {pending > 0 && !isPaused && (tps != null || etaLabel != null) && (
            <span style={{ fontSize: 11, color: '#9c27b0', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
              {tps != null && `${tps} tok/s`}{tps != null && etaLabel && ' · '}{etaLabel}
            </span>
          )}
          {pending > 0 && !isPaused && (
            <Button size="sm" variant="secondary" loading={stopEnrichMut.isPending}
              onClick={() => stopEnrichMut.mutate()}
              style={{ fontSize: 11, padding: '3px 10px', flexShrink: 0 }}>
              ⏹ Stop
            </Button>
          )}
          {pending > 0 && isPaused && (
            <Button size="sm" variant="secondary" loading={enrichMut.isPending}
              onClick={() => enrichMut.mutate()}
              style={{ fontSize: 11, padding: '3px 10px', flexShrink: 0 }}>
              ▶ Resume
            </Button>
          )}
          {pending === 0 && (
            <Button size="sm" variant="secondary"
              loading={reEnrichMut.isPending}
              onClick={() => reEnrichMut.mutate()}
              style={{ fontSize: 11, padding: '3px 10px', flexShrink: 0 }}>
              ↺ Re-enrich all
            </Button>
          )}
          {enrichError && (
            <span style={{ fontSize: 12, color: '#c62828', flex: '1 1 100%', marginTop: 4 }}>
              ⚠ {enrichError}
            </span>
          )}
        </div>
      )}

      <ArticleFilters
        sources={sources}
        categories={categories}
        filters={filters}
        onChange={handleFilterChange}
      />

      {scrapeMut.isSuccess && (
        <p style={{ fontSize: 13, color: 'var(--brand-color)', background: 'var(--brand-color-light)', padding: '8px 12px', borderRadius: 6 }}>
          Scrape triggered — new articles will appear shortly.
        </p>
      )}

      <ArticleFeed
        articles={data?.items ?? []}
        isLoading={isLoading}
        page={page}
        pages={data?.pages ?? 0}
        total={data?.total ?? 0}
        onPageChange={setPage}
        onMarkRead={(id) => markReadMut.mutate(id)}
        onReEnrich={(id) => reEnrichSingleMut.mutate(id)}
      />
    </div>
  )
}
