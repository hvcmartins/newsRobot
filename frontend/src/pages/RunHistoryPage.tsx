import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTenant } from '@/contexts/TenantContext'
import { scrapeRunApi } from '@/api/scrapeRuns'
import RunHistoryTable from '@/components/scrapeRuns/RunHistoryTable'
import Button from '@/components/ui/Button'

export default function RunHistoryPage() {
  const { activeTenant } = useTenant()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const tenantId = activeTenant?.id ?? 0

  const { data, isLoading } = useQuery({
    queryKey: ['scrape-runs', tenantId, page],
    queryFn: () => scrapeRunApi.list(tenantId, page),
    enabled: !!tenantId,
    refetchInterval: 10_000,
  })

  const triggerMut = useMutation({
    mutationFn: () => scrapeRunApi.triggerFull(tenantId),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['scrape-runs', tenantId] }), 2000),
  })

  if (!activeTenant) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Run History</h1>
          <p style={{ fontSize: 13, color: '#888', marginTop: 2 }}>Scrape runs for {activeTenant.name}</p>
        </div>
        <Button loading={triggerMut.isPending} onClick={() => triggerMut.mutate()}>
          🔄 Trigger Full Scrape
        </Button>
      </div>

      {triggerMut.isSuccess && (
        <p style={{ fontSize: 13, color: 'var(--brand-color)', background: 'var(--brand-color-light)', padding: '8px 12px', borderRadius: 6 }}>
          Scrape triggered — this page auto-refreshes every 10 seconds.
        </p>
      )}

      {isLoading ? <p style={{ color: '#999' }}>Loading…</p> : (
        <RunHistoryTable runs={data?.items ?? []} />
      )}

      {data && data.total > data.size && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</Button>
          <span style={{ fontSize: 13, color: '#666', padding: '5px 0' }}>Page {page}</span>
          <Button variant="secondary" size="sm" disabled={(data.items.length < data.size)} onClick={() => setPage(p => p + 1)}>Next →</Button>
        </div>
      )}
    </div>
  )
}
