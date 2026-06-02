import React from 'react'
import type { Article } from '@/api/types'
import ArticleCard from './ArticleCard'
import Spinner from '@/components/ui/Spinner'
import Button from '@/components/ui/Button'

interface Props {
  articles: Article[]
  isLoading: boolean
  page: number
  pages: number
  total: number
  onPageChange: (p: number) => void
  onMarkRead: (id: number) => void
  onReEnrich?: (id: number) => void
}

const _UNCATEGORIZED = new Set(['Uncategorized', 'Other', '', undefined, null])

function groupByCategory(articles: Article[]): Array<[string, Article[]]> {
  const map = new Map<string, Article[]>()
  for (const a of articles) {
    const cat = (a.category && !_UNCATEGORIZED.has(a.category)) ? a.category : 'General'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(a)
  }
  return [...map.entries()].sort(([a], [b]) => {
    if (a === 'General') return 1
    if (b === 'General') return -1
    return a.localeCompare(b)
  })
}

const grid: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
  gap: 16,
}

export default function ArticleFeed({
  articles, isLoading, page, pages, total, onPageChange, onMarkRead, onReEnrich,
}: Props) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spinner size={36} />
      </div>
    )
  }

  if (!articles.length) {
    return (
      <div style={{ textAlign: 'center', padding: 64, color: '#999' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📭</div>
        <p>No articles found. Try triggering a scrape or adjusting filters.</p>
      </div>
    )
  }

  const hasCategories = articles.some(a => a.category && !_UNCATEGORIZED.has(a.category))
  const groups = hasCategories ? groupByCategory(articles) : null

  const pagination = pages > 1 && (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 24 }}>
      <Button variant="secondary" size="sm" disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}>← Prev</Button>
      <span style={{ fontSize: 13, color: '#666' }}>Page {page} of {pages} ({total} total)</span>
      <Button variant="secondary" size="sm" disabled={page >= pages}
        onClick={() => onPageChange(page + 1)}>Next →</Button>
    </div>
  )

  if (groups) {
    return (
      <div>
        {groups.map(([cat, catArticles]) => (
          <div key={cat} style={{ marginBottom: 32 }}>
            {cat !== 'General' && (
              <div style={{
                borderLeft: '3px solid var(--brand-color)',
                paddingLeft: 12,
                marginBottom: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--brand-color)' }}>
                  {cat}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, background: 'var(--brand-color)', color: '#fff',
                  padding: '1px 6px', borderRadius: 8, minWidth: 18, textAlign: 'center',
                }}>
                  {catArticles.length}
                </span>
              </div>
            )}
            <div style={grid}>
              {catArticles.map(a => (
                <ArticleCard key={a.id} article={a} onMarkRead={onMarkRead} onReEnrich={onReEnrich} />
              ))}
            </div>
          </div>
        ))}
        {pagination}
      </div>
    )
  }

  return (
    <div>
      <div style={{ ...grid, marginBottom: 24 }}>
        {articles.map(a => (
          <ArticleCard key={a.id} article={a} onMarkRead={onMarkRead} onReEnrich={onReEnrich} />
        ))}
      </div>
      {pagination}
    </div>
  )
}
