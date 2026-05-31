import React from 'react'
import Modal from '@/components/ui/Modal'
import Badge from '@/components/ui/Badge'

interface SampleArticle {
  title: string
  url: string
  excerpt: string | null
  published_at: string | null
  image_url: string | null
}

interface TestData {
  source_name?: string
  articles_found?: number
  sample?: SampleArticle[]
  error?: string
}

interface Props {
  data: unknown
  onClose: () => void
}

export default function SourceTestResult({ data, onClose }: Props) {
  const td = data as TestData

  return (
    <Modal title="Source Test Result" onClose={onClose} width={600}>
      {td.error ? (
        <div style={{ color: '#e53935', background: '#ffebee', padding: 14, borderRadius: 8 }}>
          {td.error}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p style={{ color: '#555', fontSize: 13 }}>
            Found <strong>{td.articles_found}</strong> articles from <strong>{td.source_name}</strong>.
            Showing up to 5 samples:
          </p>
          {(td.sample ?? []).map((a, i) => (
            <div key={i} style={{ border: '1px solid #eee', borderRadius: 8, padding: 12 }}>
              {a.image_url && (
                <img src={a.image_url} alt="" style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 6, marginBottom: 8 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
              )}
              <a href={a.url} target="_blank" rel="noopener" style={{ fontWeight: 600, fontSize: 14, color: 'var(--brand-color)' }}>
                {a.title}
              </a>
              {a.excerpt && <p style={{ fontSize: 12, color: '#666', marginTop: 4, lineHeight: 1.5 }}>{a.excerpt.slice(0, 200)}…</p>}
              {a.published_at && <p style={{ fontSize: 11, color: '#aaa', marginTop: 6 }}>{new Date(a.published_at).toLocaleString()}</p>}
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
