import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTenant } from '@/contexts/TenantContext'
import { sourceApi } from '@/api/sources'
import SourceList from '@/components/sources/SourceList'
import SourceForm from '@/components/sources/SourceForm'
import Button from '@/components/ui/Button'

export default function SourcesPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const tenantId = activeTenant?.id ?? 0

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['sources', tenantId],
    queryFn: () => sourceApi.list(tenantId),
    enabled: !!tenantId,
  })

  const createMut = useMutation({
    mutationFn: sourceApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources', tenantId] }),
  })

  if (!activeTenant) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>My Sources</h1>
          <p style={{ fontSize: 13, color: '#888', marginTop: 2 }}>{sources.length} source{sources.length !== 1 ? 's' : ''} configured</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/source-library">
            <Button variant="secondary" size="sm">📚 Browse Library</Button>
          </Link>
          <Button size="sm" onClick={() => setShowAdd(true)}>+ Add Custom Source</Button>
        </div>
      </div>

      {isLoading ? (
        <p style={{ color: '#999' }}>Loading…</p>
      ) : (
        <SourceList sources={sources} tenantId={tenantId} />
      )}

      {showAdd && (
        <SourceForm
          initial={{ tenant_id: tenantId }}
          onSave={async (data) => { await createMut.mutateAsync(data) }}
          onClose={() => setShowAdd(false)}
        />
      )}
    </div>
  )
}
