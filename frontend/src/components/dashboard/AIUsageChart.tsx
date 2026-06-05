import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { aiUsageApi, AIUsageView, AIUsageBucket } from '@/api/aiUsage'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`
  return n.toString()
}

function fmtBucketLabel(ts: string, view: AIUsageView): string {
  const d = parseUTC(ts)
  if (view === 'minute') return format(d, 'HH:mm')
  if (view === 'hour') return format(d, 'HH:mm')
  return format(d, 'MMM d')
}

function getNiceTicks(maxVal: number, n: number = 4): number[] {
  if (maxVal === 0) return [0]
  if (maxVal <= n) return Array.from({ length: Math.ceil(maxVal) + 1 }, (_, i) => i)
  const step = maxVal / n
  const magnitude = Math.pow(10, Math.floor(Math.log10(step)))
  const niceStep = Math.ceil(step / magnitude) * magnitude
  return Array.from({ length: n + 1 }, (_, i) => Math.round(niceStep * i))
}

const VIEW_LABELS: Record<AIUsageView, string> = {
  minute: 'Last hour',
  hour: 'Last 24h',
  day: 'Last 30d',
}

// ── Single chart panel ────────────────────────────────────────────────────────

interface PanelProps {
  title: string
  todayLabel: string
  buckets: AIUsageBucket[]
  getValue: (b: AIUsageBucket) => number
  barColor: string
  view: AIUsageView
}

const SVG_W = 500
const CHART_H = 90
const Y_AXIS_W = 42
const BOTTOM_H = 18

function BarChartPanel({ title, todayLabel, buckets, getValue, barColor, view }: PanelProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  const values = buckets.map(getValue)
  const maxVal = Math.max(...values, 1)
  const ticks = getNiceTicks(maxVal, 4)
  const n = buckets.length || 1
  const chartW = SVG_W - Y_AXIS_W - 6
  const barPitch = chartW / n
  const barW = Math.max(1, barPitch - 1)

  const displayVal = hovered !== null ? fmtNumber(values[hovered]) : todayLabel
  const displaySub = hovered !== null
    ? fmtBucketLabel(buckets[hovered].ts, view)
    : VIEW_LABELS[view].toLowerCase()

  return (
    <div style={{
      background: '#fff', borderRadius: 10,
      border: '1px solid #eee',
      padding: '16px 18px 10px',
      display: 'flex', flexDirection: 'column', gap: 0,
      boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
    }}>
      {/* Panel header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#333' }}>{title}</span>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: barColor, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
            {displayVal}
          </div>
          <div style={{ fontSize: 10, color: '#aaa', marginTop: 3, letterSpacing: '0.3px' }}>
            {displaySub}
          </div>
        </div>
      </div>

      {/* SVG chart */}
      <svg
        viewBox={`0 0 ${SVG_W} ${CHART_H + BOTTOM_H}`}
        style={{ width: '100%', display: 'block' }}
        onMouseLeave={() => setHovered(null)}
      >
        {/* Subtle Y-axis grid lines + tick labels */}
        {ticks.map((tick, ti) => {
          const y = CHART_H - (tick / maxVal) * CHART_H
          return (
            <g key={ti}>
              <line
                x1={Y_AXIS_W} x2={SVG_W - 6} y1={y} y2={y}
                stroke="rgba(0,0,0,0.05)" strokeWidth={1}
              />
              <text
                x={Y_AXIS_W - 5} y={y + 3.5}
                textAnchor="end" fill="#bbb" fontSize={9}
                fontFamily="ui-monospace,monospace"
              >
                {fmtNumber(tick)}
              </text>
            </g>
          )
        })}

        {/* Dashed baseline */}
        <line
          x1={Y_AXIS_W} x2={SVG_W - 6} y1={CHART_H} y2={CHART_H}
          stroke={barColor} strokeWidth={1} strokeDasharray="3 5" opacity={0.3}
        />

        {/* Bars */}
        {buckets.map((b, i) => {
          const val = getValue(b)
          const barH = val > 0 ? Math.max(2, (val / maxVal) * CHART_H) : 0
          const x = Y_AXIS_W + i * barPitch
          return (
            <rect
              key={i}
              x={x} y={CHART_H - barH}
              width={barW} height={barH}
              fill={hovered === i ? '#333' : barColor}
              rx={1}
              onMouseEnter={() => setHovered(i)}
              style={{ cursor: 'crosshair' }}
            />
          )
        })}

        {/* Transparent hit-areas covering full chart height so hover works even on empty buckets */}
        {buckets.map((_, i) => (
          <rect
            key={`hit-${i}`}
            x={Y_AXIS_W + i * barPitch} y={0}
            width={barPitch} height={CHART_H}
            fill="transparent"
            onMouseEnter={() => setHovered(i)}
          />
        ))}

        {/* X-axis: first and last label only */}
        {buckets.length > 1 && <>
          <text
            x={Y_AXIS_W} y={CHART_H + BOTTOM_H - 3}
            fill="#bbb" fontSize={9} fontFamily="ui-monospace,monospace"
          >
            {fmtBucketLabel(buckets[0].ts, view)}
          </text>
          <text
            x={SVG_W - 6} y={CHART_H + BOTTOM_H - 3}
            textAnchor="end" fill="#3a3a3a" fontSize={9} fontFamily="ui-monospace,monospace"
          >
            {fmtBucketLabel(buckets[buckets.length - 1].ts, view)}
          </text>
        </>}
      </svg>
    </div>
  )
}

// ── Exported component ────────────────────────────────────────────────────────

interface Props {
  tenantId?: number
}

export default function AIUsageChart({ tenantId }: Props) {
  const [view, setView] = useState<AIUsageView>('hour')

  const { data, isLoading } = useQuery({
    queryKey: ['ai-usage', view, tenantId],
    queryFn: () => aiUsageApi.get(view, tenantId),
    enabled: !!tenantId,
    refetchInterval: view === 'minute' ? 30_000 : 60_000,
  })

  const buckets = data?.buckets ?? []

  // Aggregate totals for the selected view window (what the charts show)
  const periodCalls = buckets.reduce((s, b) => s + b.calls, 0)
  const periodTokensIn = buckets.reduce((s, b) => s + b.tokens_in, 0)
  const periodTokensOut = buckets.reduce((s, b) => s + b.tokens_out, 0)
  const periodTokens = periodTokensIn + periodTokensOut

  // For "last hour" view use the in-memory today count; for wider views use bucket sum
  const today = data?.today ?? { calls: 0, tokens_in: 0, tokens_out: 0 }
  const displayCalls = view === 'minute'
    ? Math.max(data?.today_db_calls ?? 0, today.calls)
    : periodCalls
  const displayTokensIn = view === 'minute' ? today.tokens_in : periodTokensIn
  const displayTokensOut = view === 'minute' ? today.tokens_out : periodTokensOut
  const displayTokens = displayTokensIn + displayTokensOut

  const periodLabel = VIEW_LABELS[view].toLowerCase()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: '#aaa' }}>
          AI API Usage
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          {(Object.keys(VIEW_LABELS) as AIUsageView[]).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
                border: '1px solid',
                borderColor: view === v ? '#555' : '#e0e0e0',
                background: view === v ? '#f5f5f5' : '#fff',
                color: view === v ? '#333' : '#888',
                cursor: 'pointer',
              }}
            >
              {VIEW_LABELS[v]}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[0, 1].map(i => (
            <div key={i} style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, height: 160,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
              <span style={{ fontSize: 12, color: '#ccc' }}>Loading…</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <BarChartPanel
            title="API Calls"
            todayLabel={displayCalls.toLocaleString()}
            buckets={buckets}
            getValue={b => b.calls}
            barColor="#4ade80"
            view={view}
          />
          <BarChartPanel
            title="Tokens"
            todayLabel={fmtNumber(displayTokens)}
            buckets={buckets}
            getValue={b => b.tokens_in + b.tokens_out}
            barColor="#a78bfa"
            view={view}
          />
        </div>
      )}

      {/* Period summary counters */}
      {!isLoading && (
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', paddingLeft: 2 }}>
          <PeriodCounter label={`Calls · ${periodLabel}`} value={displayCalls.toLocaleString()} color="#22c55e" />
          <PeriodCounter label="Tokens in" value={fmtNumber(displayTokensIn)} color="#3b82f6" />
          <PeriodCounter label="Tokens out" value={fmtNumber(displayTokensOut)} color="#a855f7" />
          <PeriodCounter label="Total tokens" value={fmtNumber(displayTokens)} color="#555" />
        </div>
      )}
    </div>
  )
}

function PeriodCounter({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#aaa' }}>
        {label}
      </span>
      <span style={{ fontSize: 18, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </div>
  )
}
