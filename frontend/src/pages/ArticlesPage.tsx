import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sourceApi } from '@/api/sources'
import { scrapeRunApi } from '@/api/scrapeRuns'
import ArticleFeed from '@/components/articles/ArticleFeed'
import ArticleFilters, { Filters } from '@/components/articles/ArticleFilters'

export default function ArticlesPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [filters, setFilters] = useState<Filters>({})

  const tenantId = activeTenant?.id ?? 0

  const { data: sources = [] } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['articles', tenantId, filters],
    queryFn: () => articleApi.list({ tenant_id: tenantId, ...filters, page: 1, size: 200 }),
    enabled: !!tenantId,
  })

  const { data: dashboard } = useQuery({
    queryKey: ['dashboard', tenantId],
    queryFn: () => articleApi.dashboard(tenantId),
    enabled: !!tenantId,
    refetchInterval: 60_000,
  })

  const categoryOrder: string[] = React.useMemo(() => {
    try { return JSON.parse(activeTenant?.ai_categories ?? '[]') } catch { return [] }
  }, [activeTenant?.ai_categories])

  const { data: rawCategories = [] } = useQuery({
    queryKey: ['article-categories', tenantId],
    queryFn: () => articleApi.categories(tenantId),
    enabled: !!tenantId,
  })

  const categories = React.useMemo(() => {
    const orderIdx = new Map(categoryOrder.map((c, i) => [c, i]))
    return [...rawCategories].sort((a, b) => {
      const ia = orderIdx.has(a) ? orderIdx.get(a)! : categoryOrder.length
      const ib = orderIdx.has(b) ? orderIdx.get(b)! : categoryOrder.length
      return ia !== ib ? ia - ib : a.localeCompare(b)
    })
  }, [rawCategories, categoryOrder])

  const markReadMut = useMutation({
    mutationFn: articleApi.markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const reEnrichSingleMut = useMutation({
    mutationFn: (id: number) => articleApi.reEnrich(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
      qc.invalidateQueries({ queryKey: ['article-categories', tenantId] })
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
    },
  })

  const fetchImageMut = useMutation({
    mutationFn: (id: number) => articleApi.fetchImage(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const fetchMissingImagesMut = useMutation({
    mutationFn: () => articleApi.fetchMissingImages(tenantId),
    onSuccess: (res) => {
      if (res.queued > 0) {
        setTimeout(() => qc.invalidateQueries({ queryKey: ['articles', tenantId] }), 8_000)
      }
    },
  })

  const [refreshLabel, setRefreshLabel] = useState<'idle' | 'scraping' | 'enriching' | 'done'>('idle')

  const handleRefresh = useCallback(async () => {
    if (refreshLabel !== 'idle') return
    try {
      setRefreshLabel('scraping')
      await scrapeRunApi.triggerFull(tenantId)
      setRefreshLabel('enriching')
      await articleApi.triggerEnrich(tenantId)
      setRefreshLabel('done')
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['articles', tenantId] })
        qc.invalidateQueries({ queryKey: ['article-categories', tenantId] })
        qc.invalidateQueries({ queryKey: ['dashboard', tenantId] })
        setRefreshLabel('idle')
      }, 3_000)
    } catch {
      setRefreshLabel('idle')
    }
  }, [tenantId, refreshLabel, qc])

  const missingImageCount = (data?.items ?? []).filter((a) => !a.image_url).length

  const handleFilterChange = useCallback((f: Filters) => setFilters(f), [])

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select or create a tenant to get started.</div>
  }

  const scrapePaused = activeTenant?.scrape_paused ?? false
  const nextSend = dashboard?.next_send_at
    ? formatDistanceToNow(parseUTC(dashboard.next_send_at), { addSuffix: true })
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>News Queue</h1>
          <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
            {data?.total != null
              ? `${data.total} article${data.total !== 1 ? 's' : ''} pending`
              : 'Pending articles awaiting your next digest'}
            {nextSend && !scrapePaused && (
              <span style={{ marginLeft: 8, color: 'var(--brand-color)', fontWeight: 500 }}>
                · Next send {nextSend}
              </span>
            )}
            {scrapePaused && (
              <span style={{ marginLeft: 8, color: '#795548', fontWeight: 500 }}>
                · Scraping paused
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, marginTop: 4 }}>
          {missingImageCount > 0 && (
            <button
              onClick={() => fetchMissingImagesMut.mutate()}
              disabled={fetchMissingImagesMut.isPending || fetchMissingImagesMut.isSuccess}
              style={{
                padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                border: '1px solid #e0e0e0', cursor: fetchMissingImagesMut.isPending || fetchMissingImagesMut.isSuccess ? 'default' : 'pointer',
                background: fetchMissingImagesMut.isSuccess ? '#f0fdf4' : '#fff',
                color: fetchMissingImagesMut.isSuccess ? '#16a34a' : '#555',
              }}
            >
              {fetchMissingImagesMut.isPending
                ? 'Queuing…'
                : fetchMissingImagesMut.isSuccess
                  ? `✓ Fetching ${fetchMissingImagesMut.data?.queued ?? missingImageCount} images`
                  : `🖼 Fetch ${missingImageCount} missing image${missingImageCount !== 1 ? 's' : ''}`}
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshLabel !== 'idle'}
            style={{
              padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              border: '1px solid var(--brand-color)',
              cursor: refreshLabel !== 'idle' ? 'default' : 'pointer',
              background: refreshLabel === 'done' ? '#f0fdf4' : 'var(--brand-color)',
              color: refreshLabel === 'done' ? '#16a34a' : '#fff',
              opacity: refreshLabel !== 'idle' ? 0.8 : 1,
            }}
          >
            {refreshLabel === 'scraping' ? 'Scraping…'
              : refreshLabel === 'enriching' ? 'Enriching…'
              : refreshLabel === 'done' ? '✓ Refreshed'
              : '↺ Re-scrape & Enrich'}
          </button>
        </div>
      </div>

      <ArticleFilters
        sources={sources}
        categories={categories}
        filters={filters}
        onChange={handleFilterChange}
      />

      <ArticleFeed
        articles={data?.items ?? []}
        isLoading={isLoading}
        total={data?.total ?? 0}
        onMarkRead={(id) => markReadMut.mutate(id)}
        onReEnrich={(id) => reEnrichSingleMut.mutate(id)}
        onFetchImage={(id) => fetchImageMut.mutate(id)}
      />
    </div>
  )
}
