import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, formatDistanceToNow } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sourceApi } from '@/api/sources'
import type { Article } from '@/api/types'
import Badge from '@/components/ui/Badge'
import Spinner from '@/components/ui/Spinner'
import Button from '@/components/ui/Button'

function groupByDigest(articles: Article[]): Array<{ digestId: number | null; date: string; articles: Article[] }> {
  const map = new Map<string, Article[]>()
  for (const a of articles) {
    const key = a.digest_id != null ? `digest-${a.digest_id}` : `date-${a.archived_at?.slice(0, 10) ?? 'unknown'}`
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(a)
  }
  return [...map.entries()].map(([key, arts]) => ({
    digestId: key.startsWith('digest-') ? parseInt(key.slice(7)) : null,
    date: arts[0].archived_at ?? arts[0].scraped_at,
    articles: arts,
  }))
}

function ArchivedArticleRow({ article }: { article: Article }) {
  const displayText = article.summary || article.excerpt
  const date = article.published_at || article.scraped_at

  return (
    <div style={{
      display: 'flex', gap: 12, padding: '12px 0',
      borderBottom: '1px solid #f0f0f0', alignItems: 'flex-start',
    }}>
      {article.image_url && (
        <a href={article.url} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
          <img
            src={article.image_url}
            alt=""
            loading="lazy"
            style={{ width: 64, height: 48, objectFit: 'cover', borderRadius: 4, display: 'block' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        </a>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: '#aaa', fontWeight: 500 }}>{article.source.name}</span>
          {article.category && !['Uncategorized', 'Other'].includes(article.category) && (
            <Badge variant="neutral">{article.category}</Badge>
          )}
          {article.relevance_score > 0 && article.ai_enriched && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
              background: article.relevance_score >= 0.7 ? '#e8f5e9' : '#fff3e0',
              color: article.relevance_score >= 0.7 ? '#2e7d32' : '#e65100',
            }}>
              {Math.round(article.relevance_score * 100)}%
            </span>
          )}
        </div>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', display: 'block', marginBottom: 4 }}
        >
          {article.title}
        </a>
        {displayText && (
          <p style={{
            fontSize: 12, color: '#666', lineHeight: 1.5, margin: 0,
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {displayText}
          </p>
        )}
      </div>
      <span style={{ fontSize: 11, color: '#bbb', flexShrink: 0, whiteSpace: 'nowrap' }}>
        {formatDistanceToNow(parseUTC(date), { addSuffix: true })}
      </span>
    </div>
  )
}

export default function ArchivePage() {
  const { activeTenant } = useTenant()
  const [page, setPage] = useState(1)
  const [sourceFilter, setSourceFilter] = useState<number | undefined>()
  const [keywordFilter, setKeywordFilter] = useState('')

  const tenantId = activeTenant?.id ?? 0

  const { data: sources = [] } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['archive', tenantId, page, sourceFilter, keywordFilter],
    queryFn: () => articleApi.list({
      tenant_id: tenantId,
      archived: true,
      page,
      size: 50,
      source_id: sourceFilter,
      keyword: keywordFilter || undefined,
    }),
    enabled: !!tenantId,
  })

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select a tenant to view the archive.</div>
  }

  const groups = data?.items ? groupByDigest(data.items) : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Archive</h1>
          <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
            {data?.total != null ? `${data.total} archived articles across all sent digests` : 'Articles sent by email digest'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          placeholder="Search..."
          value={keywordFilter}
          onChange={(e) => { setKeywordFilter(e.target.value); setPage(1) }}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, minWidth: 180, background: '#fff' }}
        />
        <select
          value={sourceFilter ?? ''}
          onChange={(e) => { setSourceFilter(e.target.value ? Number(e.target.value) : undefined); setPage(1) }}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, background: '#fff' }}
        >
          <option value="">All sources</option>
          {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {(keywordFilter || sourceFilter) && (
          <button
            onClick={() => { setKeywordFilter(''); setSourceFilter(undefined); setPage(1) }}
            style={{ fontSize: 12, color: 'var(--brand-color)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <Spinner size={36} />
        </div>
      ) : !data?.items.length ? (
        <div style={{ textAlign: 'center', padding: 64, color: '#999' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🗂</div>
          <p>No archived articles yet. Articles move here after a digest is sent.</p>
        </div>
      ) : (
        <>
          {groups.map((group, i) => (
            <div key={i} style={{ background: '#fff', borderRadius: 10, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--brand-color)', flexShrink: 0 }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#333' }}>
                  Digest sent {format(parseUTC(group.date), 'PPP')}
                </span>
                <span style={{
                  fontSize: 11, background: '#f0f4ff', color: '#3a5fbb',
                  padding: '2px 8px', borderRadius: 10, fontWeight: 600,
                }}>
                  {group.articles.length} article{group.articles.length !== 1 ? 's' : ''}
                </span>
              </div>
              {group.articles.map((a) => (
                <ArchivedArticleRow key={a.id} article={a} />
              ))}
            </div>
          ))}

          {(data?.pages ?? 0) > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</Button>
              <span style={{ fontSize: 13, color: '#666' }}>Page {page} of {data?.pages} ({data?.total} total)</span>
              <Button variant="secondary" size="sm" disabled={page >= (data?.pages ?? 1)} onClick={() => setPage(p => p + 1)}>Next →</Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
