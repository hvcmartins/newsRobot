import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow, format } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { useTenant } from '@/contexts/TenantContext'
import { articleApi } from '@/api/articles'
import { sourceApi } from '@/api/sources'
import { tenantApi } from '@/api/tenants'
import { scrapeRunApi } from '@/api/scrapeRuns'
import Button from '@/components/ui/Button'
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

function ProgressBar({ pct, color, trackColor }: { pct: number; color: string; trackColor: string }) {
  return (
    <div style={{ flex: 1, minWidth: 80, height: 6, borderRadius: 3, background: trackColor }}>
      <div style={{
        width: `${Math.min(100, pct)}%`, height: '100%', borderRadius: 3,
        background: color, transition: 'width 0.5s ease',
      }} />
    </div>
  )
}

export default function DashboardPage() {
  const { activeTenant, refreshTenants } = useTenant()
  const qc = useQueryClient()
  const tenantId = activeTenant?.id ?? 0

  // ── Data queries ──────────────────────────────────────────────────────────
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', tenantId],
    queryFn: () => articleApi.dashboard(tenantId),
    enabled: !!tenantId,
    refetchInterval: 30_000,
  })

  const { data: scrapeStatus } = useQuery({
    queryKey: ['scrape-status', tenantId],
    queryFn: () => scrapeRunApi.status(tenantId),
    enabled: !!tenantId,
    refetchInterval: (q) => q.state.data?.is_running ? 2000 : 5000,
  })

  const { data: enrichStatus } = useQuery({
    queryKey: ['enrichment-status', tenantId],
    queryFn: () => articleApi.enrichmentStatus(tenantId),
    enabled: !!tenantId,
    refetchInterval: (q) => (q.state.data?.pending ?? 0) > 0 ? 3000 : 10000,
  })

  // ── Scrape mutations ──────────────────────────────────────────────────────
  const scrapeNowMut = useMutation({
    mutationFn: () => sourceApi.scrapeAllNow(tenantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scrape-status', tenantId] })
      qc.invalidateQueries({ queryKey: ['dashboard', tenantId] })
    },
  })

  const pauseMut = useMutation({
    mutationFn: () => tenantApi.pauseScrape(activeTenant!.slug),
    onSuccess: () => refreshTenants(),
  })

  const resumeMut = useMutation({
    mutationFn: async () => {
      await tenantApi.resumeScrape(activeTenant!.slug)
      await sourceApi.scrapeAllNow(tenantId)
    },
    onSuccess: () => {
      refreshTenants()
      qc.invalidateQueries({ queryKey: ['scrape-status', tenantId] })
      qc.invalidateQueries({ queryKey: ['dashboard', tenantId] })
    },
  })

  // ── Enrichment mutations ──────────────────────────────────────────────────
  const [enrichError, setEnrichError] = useState<string | null>(null)

  const enrichMut = useMutation({
    mutationFn: () => articleApi.triggerEnrich(tenantId, false),
    onSuccess: (res) => {
      setEnrichError(null)
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
      if (res.queued === 0) setEnrichError('No pending articles — use Re-enrich to reprocess all.')
    },
    onError: (err: Error) => setEnrichError(err.message),
  })

  const stopEnrichMut = useMutation({
    mutationFn: () => articleApi.stopEnrich(tenantId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] }),
  })

  const reEnrichMut = useMutation({
    mutationFn: () => articleApi.triggerEnrich(tenantId, true),
    onSuccess: () => {
      setEnrichError(null)
      qc.invalidateQueries({ queryKey: ['enrichment-status', tenantId] })
      qc.invalidateQueries({ queryKey: ['articles', tenantId] })
    },
    onError: (err: Error) => setEnrichError(err.message),
  })

  // ── Derived values ────────────────────────────────────────────────────────
  if (!activeTenant) {
    return <div style={{ padding: 48, textAlign: 'center', color: '#999' }}>Select a tenant to view the dashboard.</div>
  }

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner size={36} /></div>
  }

  const scrapePaused = activeTenant?.scrape_paused ?? false
  const scrapeRunning = scrapeStatus?.is_running ?? false
  const scrapeTotal = scrapeStatus?.total ?? 0
  const scrapeDone = scrapeStatus?.done ?? 0
  const scrapePct = scrapeTotal > 0 ? Math.round((scrapeDone / scrapeTotal) * 100) : 0
  const scrapeNewToday = scrapeStatus?.articles_new ?? 0

  const enrichPending = enrichStatus?.pending ?? 0
  const enrichTotal = enrichStatus?.total ?? 0
  const enriched = enrichStatus?.enriched ?? 0
  const enrichPct = enrichTotal > 0 ? Math.round((enriched / enrichTotal) * 100) : 0
  const enrichPaused = enrichStatus?.paused ?? false
  const tps: number | null = enrichStatus?.tokens_per_second ?? null
  const secsPerArticle: number | null = enrichStatus?.seconds_per_article ?? null
  const etaSecs = secsPerArticle != null && enrichPending > 0 ? Math.ceil(secsPerArticle * enrichPending) : null
  const etaLabel = etaSecs == null ? null
    : etaSecs < 60 ? `~${etaSecs}s left`
    : `~${Math.ceil(etaSecs / 60)}min left`

  const enrichRate = data?.enrichment_rate != null ? `${data.enrichment_rate}%` : '—'
  const lastDigestLabel = data?.last_digest_at
    ? formatDistanceToNow(parseUTC(data.last_digest_at), { addSuffix: true })
    : 'Never'
  const nextSendLabel = data?.next_send_at
    ? formatDistanceToNow(parseUTC(data.next_send_at), { addSuffix: true })
    : 'Not scheduled'
  const nextSendFull = data?.next_send_at ? format(parseUTC(data.next_send_at), 'PPpp') : null
  const nextScrapeLabel = data?.next_scrape_at
    ? formatDistanceToNow(parseUTC(data.next_scrape_at), { addSuffix: true })
    : null
  const nextScrapeFull = data?.next_scrape_at ? format(parseUTC(data.next_scrape_at), 'PPpp') : null
  const runsTotal = (data?.recent_runs_ok ?? 0) + (data?.recent_runs_error ?? 0)
  const healthColor = (data?.recent_runs_error ?? 0) === 0 ? '#2e7d32'
    : (data?.recent_runs_ok ?? 0) === 0 ? '#c62828' : '#e65100'
  const healthLabel = runsTotal === 0 ? 'No runs yet'
    : (data?.recent_runs_error ?? 0) === 0 ? 'All healthy'
    : `${data?.recent_runs_error} error${(data?.recent_runs_error ?? 0) !== 1 ? 's' : ''} / ${runsTotal} runs`

  const panelStyle: React.CSSProperties = {
    background: '#fff', borderRadius: 10, padding: '16px 20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
    display: 'flex', flexDirection: 'column', gap: 12,
  }

  const sectionLabel: React.CSSProperties = {
    fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.8px', color: '#aaa', marginBottom: 2,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Dashboard</h1>
        <p style={{ fontSize: 13, color: '#888', margin: 0 }}>{activeTenant.name} — overview</p>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
        <StatCard label="Scraped today" value={data?.scraped_today ?? 0} sub="New articles found" color="var(--brand-color)" />
        <StatCard label="Queue size" value={data?.pending_count ?? 0} sub="Pending in queue"
          color={((data?.pending_count ?? 0) > 50) ? '#e65100' : '#333'} />
        <StatCard label="Enrichment rate" value={enrichRate} sub="AI-enriched (last 7 days)" color="#7b1fa2" />
        <StatCard label="Last digest" value={lastDigestLabel} sub={data?.last_digest_subject ?? undefined} />
        <StatCard label="Next send" value={nextSendLabel} sub={nextSendFull ?? undefined}
          color={data?.next_send_at ? 'var(--brand-color)' : '#999'} />
        <StatCard label="Source health" value={healthLabel}
          sub={runsTotal > 0 ? `Last ${runsTotal} scrape runs` : undefined} color={healthColor} />
      </div>

      {/* Operations row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Scraping panel */}
        <div style={panelStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={sectionLabel}>Scraping</span>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
              background: scrapePaused ? '#fff8e1' : scrapeRunning ? '#e8f5e9' : '#f5f5f5',
              color: scrapePaused ? '#795548' : scrapeRunning ? '#2e7d32' : '#888',
            }}>
              {scrapePaused ? '⏸ Paused' : scrapeRunning ? '● Running' : '○ Idle'}
            </span>
          </div>

          {/* Scrape progress bar */}
          {scrapeTotal > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 12, color: scrapeRunning ? '#2e7d32' : '#888', flexShrink: 0 }}>
                {scrapeRunning
                  ? `${scrapeDone} / ${scrapeTotal} sources`
                  : `${scrapeNewToday} new article${scrapeNewToday !== 1 ? 's' : ''} last run`}
              </span>
              <ProgressBar
                pct={scrapeRunning ? scrapePct : 100}
                color={scrapeRunning ? '#4caf50' : '#c8e6c9'}
                trackColor={scrapeRunning ? '#e8f5e9' : '#f5f5f5'}
              />
              {scrapeRunning && scrapeTotal > 0 && (
                <span style={{ fontSize: 11, color: '#888', flexShrink: 0 }}>{scrapePct}%</span>
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {scrapePaused ? (
              <Button size="sm" loading={resumeMut.isPending} onClick={() => resumeMut.mutate()}
                style={{ background: '#2e7d32', borderColor: '#2e7d32' }}>
                ▶ Resume & scrape
              </Button>
            ) : (
              <>
                <Button size="sm" loading={scrapeNowMut.isPending} onClick={() => scrapeNowMut.mutate()}
                  style={{
                    background: scrapeNowMut.isSuccess ? '#e8f5e9' : 'var(--brand-color)',
                    borderColor: scrapeNowMut.isSuccess ? '#a5d6a7' : 'var(--brand-color)',
                    color: scrapeNowMut.isSuccess ? '#2e7d32' : '#fff',
                  }}>
                  {scrapeNowMut.isSuccess ? '✓ Triggered' : '▶ Scrape now'}
                </Button>
                <Button variant="secondary" size="sm" loading={pauseMut.isPending}
                  onClick={() => pauseMut.mutate()}>
                  ⏸ Pause
                </Button>
              </>
            )}
          </div>

          {scrapePaused && (
            <p style={{ fontSize: 12, color: '#795548', margin: 0 }}>
              No new articles will be fetched until scraping is resumed.
            </p>
          )}

          {nextScrapeLabel && !scrapeRunning && (
            <p style={{ fontSize: 12, color: '#888', margin: 0 }}>
              <span style={{ fontWeight: 600, color: '#555' }}>Next scrape:</span>{' '}
              <span title={nextScrapeFull ?? undefined}>{nextScrapeLabel}</span>
              {nextScrapeFull && (
                <span style={{ fontSize: 11, color: '#bbb', marginLeft: 6 }}>({nextScrapeFull})</span>
              )}
            </p>
          )}
        </div>

        {/* Enrichment panel */}
        <div style={panelStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={sectionLabel}>AI Enrichment</span>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
              background: enrichPending === 0 ? '#e8f5e9' : enrichPaused ? '#f5f5f5' : '#f3e5f5',
              color: enrichPending === 0 ? '#2e7d32' : enrichPaused ? '#757575' : '#7b1fa2',
            }}>
              {enrichPending === 0 ? '✓ Complete' : enrichPaused ? '⏸ Paused' : '● Enriching'}
            </span>
          </div>

          {enrichTotal > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 12, color: enrichPending === 0 ? '#2e7d32' : enrichPaused ? '#888' : '#7b1fa2', flexShrink: 0 }}>
                {enriched} / {enrichTotal}
              </span>
              <ProgressBar
                pct={enrichPct}
                color={enrichPending === 0 ? '#4caf50' : enrichPaused ? '#9e9e9e' : '#9c27b0'}
                trackColor={enrichPending === 0 ? '#c8e6c9' : enrichPaused ? '#e0e0e0' : '#e1bee7'}
              />
              <span style={{ fontSize: 11, color: '#aaa', flexShrink: 0 }}>{enrichPct}%</span>
            </div>
          )}

          {enrichPending > 0 && !enrichPaused && (tps != null || etaLabel != null) && (
            <span style={{ fontSize: 11, color: '#9c27b0', fontVariantNumeric: 'tabular-nums' }}>
              {tps != null && `${tps} tok/s`}{tps != null && etaLabel && ' · '}{etaLabel}
            </span>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {enrichPending > 0 && !enrichPaused && (
              <Button size="sm" variant="secondary" loading={stopEnrichMut.isPending}
                onClick={() => stopEnrichMut.mutate()}>
                ⏹ Stop
              </Button>
            )}
            {enrichPending > 0 && enrichPaused && (
              <Button size="sm" variant="secondary" loading={enrichMut.isPending}
                onClick={() => enrichMut.mutate()}>
                ▶ Resume
              </Button>
            )}
            {enrichPending === 0 && (
              <Button size="sm" variant="secondary" loading={reEnrichMut.isPending}
                onClick={() => reEnrichMut.mutate()}>
                ↺ Re-enrich all
              </Button>
            )}
          </div>

          {enrichError && (
            <span style={{ fontSize: 12, color: '#c62828' }}>⚠ {enrichError}</span>
          )}
        </div>
      </div>

      {/* Error alert */}
      {data?.recent_runs_error != null && data.recent_runs_error > 0 && (
        <div style={{
          background: '#fff3e0', border: '1px solid #ffb74d', borderRadius: 8,
          padding: '12px 16px', fontSize: 13, color: '#e65100',
        }}>
          ⚠ {data.recent_runs_error} scrape run{data.recent_runs_error !== 1 ? 's' : ''} failed recently.
          Check <a href="/run-history" style={{ color: 'inherit', fontWeight: 600 }}>Run History</a> for details.
        </div>
      )}

      {/* Last digest */}
      {data?.last_digest_at && (
        <div style={{ background: '#fff', borderRadius: 10, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Last Digest</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ fontSize: 12, color: '#999', minWidth: 80 }}>Sent</span>
              <span style={{ fontSize: 12, color: '#333' }}>{format(parseUTC(data.last_digest_at), 'PPpp')}</span>
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
