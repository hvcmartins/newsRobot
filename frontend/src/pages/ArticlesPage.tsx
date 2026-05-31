import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

  const categories = React.useMemo(() => {
    const cats = new Set((data?.items ?? []).map((a) => a.category).filter(Boolean) as string[])
    return [...cats].sort()
  }, [data?.items])

  const markReadMut = useMutation({
    mutationFn: articleApi.markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const markAllReadMut = useMutation({
    mutationFn: () => articleApi.markAllRead(tenantId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles', tenantId] }),
  })

  const scrapeMut = useMutation({
    mutationFn: () => scrapeRunApi.triggerFull(tenantId),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['articles', tenantId] }), 3000)
    },
  })

  const handleFilterChange = useCallback((f: Filters) => {
    setFilters(f)
    setPage(1)
  }, [])

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select or create a tenant to get started.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>News Feed</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" size="sm" loading={markAllReadMut.isPending} onClick={() => markAllReadMut.mutate()}>
            Mark all read
          </Button>
          <Button size="sm" loading={scrapeMut.isPending} onClick={() => scrapeMut.mutate()}>
            🔄 Scrape now
          </Button>
        </div>
      </div>

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
      />
    </div>
  )
}
