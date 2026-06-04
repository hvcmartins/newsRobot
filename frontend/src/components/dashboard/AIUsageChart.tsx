import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { parseUTC } from '@/utils/dates'
import { aiUsageApi, AIUsageView } from '@/api/aiUsage'

type Metric = 'calls' | 'tokens'

interface BarProps {
  value: number
  maxVal: number
  label: string
  height: number
  width: number
  x: number
  barColor: string
  trackColor: string
}

function Bar({ value, maxVal, label, height, width, x, barColor, trackColor }: BarProps) {
  const [hover, setHover] = useState(false)
  const fillH = maxVal > 0 ? Math.max(2, Math.round((value / maxVal) * height)) : 0

  return (
    <g
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ cursor: 'default' }}
    >
      {/* Track */}
      <rect x={x} y={0} width={width} height={height} rx={1} fill={trackColor} />
      {/* Bar */}
      {fillH > 0 && (
        <rect x={x} y={height - fillH} width={width} height={fillH} rx={1} fill={barColor} />
      )}
      {/* Hover tooltip */}
      {hover && value > 0 && (
        <g>
          <rect
            x={Math.max(0, x - 24)}
            y={height - fillH - 28}
            width={52}
            height={20}
            rx={3}
            fill="#333"
            opacity={0.9}
          />
          <text
            x={Math.max(0, x - 24) + 26}
            y={height - fillH - 14}
            textAnchor="middle"
            fill="#fff"
            fontSize={9}
          >
            {value.toLocaleString()}
          </text>
          <text
            x={Math.max(0, x - 24) + 26}
            y={height - fillH - 5}
            textAnchor="middle"
            fill="#ccc"
            fontSize={8}
          >
            {label}
          </text>
        </g>
      )}
    </g>
  )
}

function fmtBucketLabel(ts: string, view: AIUsageView): string {
  const d = parseUTC(ts)
  if (view === 'minute') return format(d, 'HH:mm')
  if (view === 'hour') return format(d, 'HH:mm')
  return format(d, 'MMM d')
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

const VIEW_LABELS: Record<AIUsageView, string> = {
  minute: 'Last hour',
  hour: 'Last 24h',
  day: 'Last 30d',
}

const VIEW_TICK_EVERY: Record<AIUsageView, number> = {
  minute: 10,
  hour: 4,
  day: 5,
}

interface Props {
  tenantId?: number
}

export default function AIUsageChart({ tenantId }: Props) {
  const [view, setView] = useState<AIUsageView>('hour')
  const [metric, setMetric] = useState<Metric>('calls')

  const { data, isLoading } = useQuery({
    queryKey: ['ai-usage', view, tenantId],
    queryFn: () => aiUsageApi.get(view, tenantId),
    refetchInterval: view === 'minute' ? 30_000 : 60_000,
  })

  const CHART_H = 72
  const CHART_W = 560
  const GAP = 1

  const buckets = data?.buckets ?? []
  const n = buckets.length || 1
  const barW = Math.max(1, Math.floor((CHART_W - GAP * (n - 1)) / n))
  const barColor = metric === 'calls' ? 'var(--brand-color)' : '#9c27b0'
  const trackColor = metric === 'calls' ? '#e8f0fe' : '#f3e5f5'
  const tickEvery = VIEW_TICK_EVERY[view]

  const values = buckets.map(b =>
    metric === 'calls' ? b.calls : b.tokens_in + b.tokens_out
  )
  const maxVal = Math.max(...values, 1)

  const today = data?.today
  const todayCalls = Math.max(data?.today_db_calls ?? 0, today?.calls ?? 0)
  const todayTokensIn = today?.tokens_in ?? 0
  const todayTokensOut = today?.tokens_out ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: '#aaa' }}>
          AI API Usage
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          {/* Metric toggle */}
          {(['calls', 'tokens'] as Metric[]).map(m => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              style={{
                fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
                border: '1px solid',
                borderColor: metric === m ? (m === 'calls' ? 'var(--brand-color)' : '#9c27b0') : '#e0e0e0',
                background: metric === m ? (m === 'calls' ? '#e8f0fe' : '#f3e5f5') : '#fff',
                color: metric === m ? (m === 'calls' ? 'var(--brand-color)' : '#9c27b0') : '#888',
                cursor: 'pointer',
              }}
            >
              {m === 'calls' ? 'Calls' : 'Tokens'}
            </button>
          ))}
          {/* View toggle */}
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

      {/* Chart */}
      {isLoading ? (
        <div style={{ height: CHART_H + 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 12, color: '#bbb' }}>Loading…</span>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <svg
            width="100%"
            viewBox={`0 0 ${CHART_W} ${CHART_H + 16}`}
            style={{ display: 'block', minWidth: 320 }}
          >
            {buckets.map((b, i) => (
              <Bar
                key={i}
                value={metric === 'calls' ? b.calls : b.tokens_in + b.tokens_out}
                maxVal={maxVal}
                label={fmtBucketLabel(b.ts, view)}
                height={CHART_H}
                width={barW}
                x={i * (barW + GAP)}
                barColor={barColor}
                trackColor={trackColor}
              />
            ))}
            {/* X-axis tick labels */}
            {buckets.map((b, i) =>
              i % tickEvery === 0 ? (
                <text
                  key={i}
                  x={i * (barW + GAP) + barW / 2}
                  y={CHART_H + 13}
                  textAnchor="middle"
                  fill="#bbb"
                  fontSize={8}
                >
                  {fmtBucketLabel(b.ts, view)}
                </text>
              ) : null
            )}
          </svg>
        </div>
      )}

      {/* Today counters */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <Counter label="Today — calls" value={todayCalls.toLocaleString()} color="#333" />
        <Counter label="Tokens in" value={fmtTokens(todayTokensIn)} color="#1565c0" />
        <Counter label="Tokens out" value={fmtTokens(todayTokensOut)} color="#9c27b0" />
        <Counter label="Total tokens" value={fmtTokens(todayTokensIn + todayTokensOut)} color="#444" />
      </div>
    </div>
  )
}

function Counter({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#bbb' }}>
        {label}
      </span>
      <span style={{ fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value}</span>
    </div>
  )
}
