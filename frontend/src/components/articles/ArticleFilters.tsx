import React from 'react'
import type { Source } from '@/api/types'

export interface Filters {
  source_id?: number
  keyword?: string
  category?: string
}

interface Props {
  sources: Source[]
  categories: string[]
  filters: Filters
  onChange: (f: Filters) => void
}

export default function ArticleFilters({ sources, categories, filters, onChange }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })

  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
      <input
        placeholder="Search..."
        value={filters.keyword ?? ''}
        onChange={(e) => set({ keyword: e.target.value || undefined })}
        style={{
          padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6,
          fontSize: 13, minWidth: 180, background: '#fff',
        }}
      />

      <select
        value={filters.source_id ?? ''}
        onChange={(e) => set({ source_id: e.target.value ? Number(e.target.value) : undefined })}
        style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, background: '#fff' }}
      >
        <option value="">All sources</option>
        {sources.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>

      {categories.length > 0 && (
        <select
          value={filters.category ?? ''}
          onChange={(e) => set({ category: e.target.value || undefined })}
          style={{ padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, background: '#fff' }}
        >
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}

      {(filters.keyword || filters.source_id || filters.category) && (
        <button
          onClick={() => onChange({})}
          style={{ fontSize: 12, color: 'var(--brand-color)', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          Clear filters
        </button>
      )}
    </div>
  )
}
