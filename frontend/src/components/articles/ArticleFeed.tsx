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
}

export default function ArticleFeed({
  articles, isLoading, page, pages, total, onPageChange, onMarkRead,
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

  return (
    <div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 16,
        marginBottom: 24,
      }}>
        {articles.map((a) => (
          <ArticleCard key={a.id} article={a} onMarkRead={onMarkRead} />
        ))}
      </div>

      {pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8 }}>
          <Button variant="secondary" size="sm" disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}>← Prev</Button>
          <span style={{ fontSize: 13, color: '#666' }}>Page {page} of {pages} ({total} total)</span>
          <Button variant="secondary" size="sm" disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}>Next →</Button>
        </div>
      )}
    </div>
  )
}
