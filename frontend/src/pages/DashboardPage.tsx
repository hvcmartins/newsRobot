import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow, format } from 'date-fns'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import Spinner from '@/components/ui/Spinner'

function StatCard({
  label, value, sub, color = '#333',
}: {
  label: string
  value: React.ReactNode
  sub?: string
  color?: string
}) {
  return (
    <div style={{
      background: '#fff', borderRadius: 10, padding: '20px 24px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.8px', color: '#aaa' }}>
        {label}
      </span>
      <span style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1.2 }}>{value}</span>
      {sub && <span style={{ fontSize: 12, color: '#999' }}>{sub}</span>}
    </div>
  )
}

export default function DashboardPage() {
  const { activeTenant } = useTenant()
  const tenantId = activeTenant?.id ?? 0

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', tenantId],
    queryFn: () => articleApi.dashboard(tenantId),
    enabled: !!tenantId,
    refetchInterval: 30_000,
  })

  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select a tenant to view the dashboard.</div>
  }

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner size={36} /></div>
  }

  const enrichRate = data?.enrichment_rate != null
    ? `${Math.round(data.enrichment_rate * 100)}%`
    : '—'

  const lastDigestLabel = data?.last_digest_at
    ? formatDistanceToNow(new Date(data.last_digest_at), { addSuffix: true })
    : 'Never'

  const nextSendLabel = data?.next_send_at
    ? formatDistanceToNow(new Date(data.next_send_at), { addSuffix: true })
    : 'Not scheduled'

  const nextSendFull = data?.next_send_at
    ? format(new Date(data.next_send_at), 'PPpp')
    : null

  const runsTotal = (data?.recent_runs_ok ?? 0) + (data?.recent_runs_error ?? 0)
  const healthColor = (data?.recent_runs_error ?? 0) === 0 ? '#2e7d32'
    : (data?.recent_runs_ok ?? 0) === 0 ? '#c62828' : '#e65100'
  const healthLabel = runsTotal === 0 ? 'No runs yet'
    : (data?.recent_runs_error ?? 0) === 0 ? 'All healthy'
    : `${data?.recent_runs_error} error${(data?.recent_runs_error ?? 0) !== 1 ? 's' : ''} / ${runsTotal} runs`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Dashboard</h1>
        <p style={{ fontSize: 13, color: '#888', margin: 0 }}>{activeTenant.name} — overview</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
        <StatCard
          label="Scraped today"
          value={data?.scraped_today ?? 0}
          sub="New articles found"
          color="var(--brand-color)"
        />
        <StatCard
          label="Queue size"
          value={data?.pending_count ?? 0}
          sub="Pending in queue"
          color={((data?.pending_count ?? 0) > 50) ? '#e65100' : '#333'}
        />
        <StatCard
          label="Enrichment rate"
          value={enrichRate}
          sub="AI-enriched articles"
          color="#7b1fa2"
        />
        <StatCard
          label="Last digest"
          value={lastDigestLabel}
          sub={data?.last_digest_subject ?? undefined}
        />
        <StatCard
          label="Next send"
          value={nextSendLabel}
          sub={nextSendFull ?? undefined}
          color={data?.next_send_at ? 'var(--brand-color)' : '#999'}
        />
        <StatCard
          label="Source health"
          value={healthLabel}
          sub={runsTotal > 0 ? `Last ${runsTotal} scrape runs` : undefined}
          color={healthColor}
        />
      </div>

      {data?.recent_runs_error != null && data.recent_runs_error > 0 && (
        <div style={{
          background: '#fff3e0', border: '1px solid #ffb74d', borderRadius: 8,
          padding: '12px 16px', fontSize: 13, color: '#e65100',
        }}>
          ⚠ {data.recent_runs_error} scrape run{data.recent_runs_error !== 1 ? 's' : ''} failed recently.
          Check <a href="/run-history" style={{ color: 'inherit', fontWeight: 600 }}>Run History</a> for details.
        </div>
      )}

      {data?.last_digest_at && (
        <div style={{ background: '#fff', borderRadius: 10, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Last Digest</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ fontSize: 12, color: '#999', minWidth: 80 }}>Sent</span>
              <span style={{ fontSize: 12, color: '#333' }}>
                {format(new Date(data.last_digest_at), 'PPpp')}
              </span>
            </div>
            {data.last_digest_subject && (
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#999', minWidth: 80 }}>Subject</span>
                <span style={{ fontSize: 12, color: '#333' }}>{data.last_digest_subject}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
