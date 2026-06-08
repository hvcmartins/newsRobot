import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, formatDistanceToNow } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sentDigestApi } from '@/api/sentDigests'
import type { Article, SentDigest } from '@/api/types'
import Badge from '@/components/ui/Badge'
import Spinner from '@/components/ui/Spinner'
import Button from '@/components/ui/Button'

// ── Article row ───────────────────────────────────────────────────────────────

function ArchivedArticleRow({ article }: { article: Article }) {
  const displayText = article.summary || article.excerpt
  const date = article.published_at || article.scraped_at

  return (
    <div style={{
      display: 'flex', gap: 12, padding: '12px 0',
      borderBottom: '1px solid #f4f4f4', alignItems: 'flex-start',
    }}>
      {article.image_url && (
        <a href={article.url} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
          <img
            src={article.image_url} alt="" loading="lazy"
            style={{ width: 60, height: 44, objectFit: 'cover', borderRadius: 4, display: 'block' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        </a>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: '#bbb', fontWeight: 500 }}>{article.source.name}</span>
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
          href={article.url} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', display: 'block', marginBottom: 3 }}
        >
          {article.title}
        </a>
        {displayText && (
          <p style={{
            fontSize: 12, color: '#777', lineHeight: 1.5, margin: 0,
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {displayText}
          </p>
        )}
      </div>
      <span style={{ fontSize: 11, color: '#ccc', flexShrink: 0, whiteSpace: 'nowrap' }}>
        {formatDistanceToNow(parseUTC(date), { addSuffix: true })}
      </span>
    </div>
  )
}

// ── Digest accordion row ──────────────────────────────────────────────────────

const DIGEST_TYPE_LABEL: Record<string, string> = {
  regular: 'Digest',
  monthly: 'Monthly',
  yearly: 'Yearly',
}

interface DigestGroupProps {
  digest: SentDigest
  tenantId: number
  isExpanded: boolean
  onToggle: () => void
}

function DigestGroup({ digest, tenantId, isExpanded, onToggle }: DigestGroupProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['archive-digest', digest.id],
    queryFn: () => articleApi.list({ tenant_id: tenantId, digest_id: digest.id, size: 500 }),
    enabled: isExpanded,
  })

  const sentDate = parseUTC(digest.sent_at)
  const typeLabel = DIGEST_TYPE_LABEL[digest.digest_type] ?? digest.digest_type

  return (
    <div style={{
      background: '#fff', borderRadius: 10,
      border: '1px solid #eee',
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      overflow: 'hidden',
    }}>
      {/* Header row — always visible */}
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 18px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        {/* Chevron */}
        <span style={{
          fontSize: 12, color: '#999', flexShrink: 0, width: 16,
          transform: isExpanded ? 'rotate(90deg)' : 'none',
          transition: 'transform 0.15s ease',
          display: 'inline-block',
        }}>▶</span>

        {/* Date + subject */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#1a1a1a', marginBottom: 2 }}>
            {format(sentDate, 'PPP')}
            <span style={{
              marginLeft: 8, fontSize: 11, fontWeight: 500,
              color: '#aaa', fontVariantNumeric: 'tabular-nums',
            }}>
              {format(sentDate, 'HH:mm')} UTC
            </span>
          </div>
          {digest.subject && (
            <div style={{
              fontSize: 12, color: '#666',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              maxWidth: '60vw',
            }}>
              {digest.subject}
            </div>
          )}
        </div>

        {/* Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {digest.digest_type !== 'regular' && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
              background: digest.digest_type === 'monthly' ? '#e8f4fd' : '#fdf3e8',
              color: digest.digest_type === 'monthly' ? '#1976d2' : '#e65100',
              letterSpacing: '0.3px',
            }}>
              {typeLabel.toUpperCase()}
            </span>
          )}
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
            background: '#f5f5f5', color: '#555',
          }}>
            {digest.article_count} article{digest.article_count !== 1 ? 's' : ''}
          </span>
        </div>
      </button>

      {/* Expanded article list */}
      {isExpanded && (
        <div style={{ borderTop: '1px solid #f0f0f0', padding: '0 18px' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
              <Spinner size={28} />
            </div>
          ) : !data?.items.length ? (
            <p style={{ fontSize: 13, color: '#aaa', padding: '20px 0', textAlign: 'center' }}>
              No articles found for this digest.
            </p>
          ) : (
            <div style={{ paddingBottom: 4 }}>
              {data.items.map((a) => (
                <ArchivedArticleRow key={a.id} article={a} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Filtered (low-relevance) accordion ───────────────────────────────────────

function FilteredGroup({ tenantId }: { tenantId: number }) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['archive-filtered', tenantId],
    queryFn: () => articleApi.list({ tenant_id: tenantId, undigested: true, size: 500 }),
    enabled: expanded,
  })

  const total = data?.total ?? 0

  // Don't render at all if nothing is filtered yet (query not run)
  if (!expanded && data === undefined) {
    // Prefetch count with a lightweight query
  }

  return (
    <div style={{
      background: '#fff', borderRadius: 10,
      border: '1px solid #eee',
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      overflow: 'hidden',
      opacity: 0.8,
    }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 18px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <span style={{
          fontSize: 12, color: '#bbb', flexShrink: 0, width: 16,
          transform: expanded ? 'rotate(90deg)' : 'none',
          transition: 'transform 0.15s ease', display: 'inline-block',
        }}>▶</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#888' }}>
            Auto-filtered articles
          </div>
          <div style={{ fontSize: 12, color: '#bbb', marginTop: 2 }}>
            Enriched but below relevance threshold — never included in any digest
          </div>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
          background: '#f5f5f5', color: '#aaa',
        }}>
          {expanded && total > 0 ? `${total} article${total !== 1 ? 's' : ''}` : '…'}
        </span>
      </button>

      {expanded && (
        <div style={{ borderTop: '1px solid #f4f4f4', padding: '0 18px' }}>
          {isLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
              <Spinner size={28} />
            </div>
          ) : !data?.items.length ? (
            <p style={{ fontSize: 13, color: '#bbb', padding: '20px 0', textAlign: 'center' }}>
              No auto-filtered articles.
            </p>
          ) : (
            <div style={{ paddingBottom: 4 }}>
              {data.items.map((a) => (
                <ArchivedArticleRow key={a.id} article={a} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ArchivePage() {
  const { activeTenant } = useTenant()
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [search, setSearch] = useState('')

  const tenantId = activeTenant?.id ?? 0

  const { data, isLoading } = useQuery({
    queryKey: ['sent-digests', tenantId, page],
    queryFn: () => sentDigestApi.list(tenantId, page, 30),
    enabled: !!tenantId,
  })

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select a tenant to view the archive.</div>
  }

  const allDigests = data?.items ?? []
  const digests = search
    ? allDigests.filter((d) => d.subject?.toLowerCase().includes(search.toLowerCase()) ||
        format(parseUTC(d.sent_at), 'PPP').toLowerCase().includes(search.toLowerCase()))
    : allDigests

  const toggle = (id: number) => setExpandedId((prev) => (prev === id ? null : id))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Archive</h1>
        <p style={{ fontSize: 13, color: '#888', margin: 0 }}>
          {data?.total != null
            ? `${data.total} digest${data.total !== 1 ? 's' : ''} sent`
            : 'Articles moved here after each digest is sent'}
        </p>
      </div>

      {/* Search */}
      <input
        placeholder="Search by date or subject…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          padding: '8px 12px', border: '1px solid #ddd', borderRadius: 7,
          fontSize: 13, background: '#fff', maxWidth: 340,
        }}
      />

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spinner size={36} />
        </div>
      ) : !digests.length ? (
        <div style={{ textAlign: 'center', padding: 64, color: '#999' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🗂</div>
          <p style={{ margin: 0 }}>
            {search ? 'No digests match your search.' : 'No sent digests yet. Articles appear here after a digest is sent via Send Now or the schedule.'}
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {digests.map((digest) => (
              <DigestGroup
                key={digest.id}
                digest={digest}
                tenantId={tenantId}
                isExpanded={expandedId === digest.id}
                onToggle={() => toggle(digest.id)}
              />
            ))}
          </div>

          {(data?.pages ?? 0) > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Prev</Button>
              <span style={{ fontSize: 13, color: '#666' }}>Page {page} of {data?.pages}</span>
              <Button variant="secondary" size="sm" disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next →</Button>
            </div>
          )}
        </>
      )}

      {/* Auto-filtered articles (low relevance, no digest) */}
      {!search && <FilteredGroup tenantId={tenantId} />}

      {/* Clarification note */}
      <p style={{ fontSize: 11, color: '#bbb', margin: 0 }}>
        Articles move here when a digest is sent via <strong>Send Now</strong> or the configured schedule.
        Test emails do not archive articles.
      </p>
    </div>
  )
}
