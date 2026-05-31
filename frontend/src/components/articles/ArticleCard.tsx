import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import type { Article } from '@/api/types'
import Badge from '@/components/ui/Badge'

interface Props {
  article: Article
  onMarkRead?: (id: number) => void
}

function relevanceStyle(score: number, aiEnriched: boolean): {
  borderColor: string
  badgeBg: string
  badgeColor: string
  label: string
} | null {
  if (!aiEnriched || score <= 0) return null
  if (score >= 0.7) return {
    borderColor: '#4caf50',
    badgeBg: '#e8f5e9',
    badgeColor: '#2e7d32',
    label: `${Math.round(score * 100)}%`,
  }
  // 0.5–0.7 orange
  return {
    borderColor: '#ff9800',
    badgeBg: '#fff3e0',
    badgeColor: '#e65100',
    label: `${Math.round(score * 100)}%`,
  }
}

export default function ArticleCard({ article, onMarkRead }: Props) {
  const displayText = article.summary || article.excerpt
  const date = article.published_at || article.scraped_at
  const rel = relevanceStyle(article.relevance_score, article.ai_enriched)

  return (
    <article
      style={{
        background: '#fff',
        borderRadius: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        overflow: 'hidden',
        opacity: article.is_read ? 0.65 : 1,
        transition: 'box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: rel ? `3px solid ${rel.borderColor}` : '3px solid transparent',
      }}
    >
      {article.image_url && (
        <a href={article.url} target="_blank" rel="noopener noreferrer">
          <img
            src={article.image_url}
            alt=""
            loading="lazy"
            style={{ width: '100%', height: 180, objectFit: 'cover', display: 'block' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        </a>
      )}

      <div style={{ padding: '14px 16px', flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{
            display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
            background: 'var(--brand-color)', flexShrink: 0,
          }} />
          <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#888' }}>
            {article.source.name}
          </span>
          {article.category && !['Uncategorized', 'Other'].includes(article.category) && (
            <Badge variant="neutral">{article.category}</Badge>
          )}
          {rel && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 10,
              marginLeft: 'auto', flexShrink: 0,
              background: rel.badgeBg,
              color: rel.badgeColor,
            }}>
              {rel.label}
            </span>
          )}
        </div>

        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => onMarkRead?.(article.id)}
          style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', lineHeight: 1.4 }}
        >
          {article.title}
        </a>

        {displayText && (
          <p style={{
            fontSize: 13, color: '#666', lineHeight: 1.6, flex: 1,
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
          }}>
            {displayText}
          </p>
        )}

        {article.relevance_reason && article.ai_enriched && (
          <p style={{ fontSize: 11, color: '#999', fontStyle: 'italic', borderLeft: '2px solid #eee', paddingLeft: 8 }}>
            {article.relevance_reason}
          </p>
        )}

        <div style={{ fontSize: 11, color: '#aaa', marginTop: 'auto' }}>
          {formatDistanceToNow(new Date(date), { addSuffix: true })}
          {article.ai_enriched && <span style={{ marginLeft: 8, color: '#9c27b0' }}>✦ AI</span>}
        </div>
      </div>
    </article>
  )
}
