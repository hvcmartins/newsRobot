import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sourceApi } from '@/api/sources'
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

  const categories = React.useMemo(() => {
    const cats = new Set((data?.items ?? []).map((a) => a.category).filter(Boolean) as string[])
    return [...cats].sort()
  }, [data?.items])

  const markReadMut = useMutation({
    mutationFn: articleApi.markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const reEnrichSingleMut = useMutation({
    mutationFn: (id: number) => articleApi.reEnrich(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
    },
  })

  const handleFilterChange = useCallback((f: Filters) => setFilters(f), [])

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select or create a tenant to get started.</div>
  }

  const scrapePaused = activeTenant?.scrape_paused ?? false
  const nextSend = dashboard?.next_send_at
    ? formatDistanceToNow(new Date(dashboard.next_send_at), { addSuffix: true })
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
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
      />
    </div>
  )
}
