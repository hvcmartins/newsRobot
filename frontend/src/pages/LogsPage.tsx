import React, { useState, useEffect, useRef, useCallback } from 'react'
import { logsApi, type LogEntry } from '@/api/logs'

const POLL_MS = 1500
const MAX_ENTRIES = 2000

// ── colours ──────────────────────────────────────────────────────────────────
const LEVEL_STYLE: Record<string, React.CSSProperties> = {
  INFO:    { color: '#1e3a5f', background: '#e3f0ff' },
  WARNING: { color: '#7a4400', background: '#fff3e0' },
  ERROR:   { color: '#7f0000', background: '#ffebee' },
}

// ── log line (scraper / AI) ───────────────────────────────────────────────────
function LogLine({ entry }: { entry: LogEntry }) {
  const lvl = LEVEL_STYLE[entry.level] ?? LEVEL_STYLE.INFO
  return (
    <div style={{
      display: 'flex', gap: 8, padding: '3px 10px',
      borderBottom: '1px solid #f0f0f0', fontSize: 12, lineHeight: 1.5,
      background: entry.level === 'ERROR' ? '#fff5f5'
                : entry.level === 'WARNING' ? '#fffdf5' : '#fff',
    }}>
      <span style={{ color: '#aaa', flexShrink: 0, fontFamily: 'monospace' }}>
        {entry.ts}
      </span>
      <span style={{
        ...lvl, fontWeight: 600, fontSize: 10, borderRadius: 3,
        padding: '1px 5px', flexShrink: 0, alignSelf: 'flex-start', marginTop: 1,
      }}>
        {entry.level}
      </span>
      <span style={{ color: '#333', wordBreak: 'break-word' }}>{entry.message}</span>
    </div>
  )
}

// ── queue line ────────────────────────────────────────────────────────────────
// Message format: "+ Title  ·  Category  ·  75%"
function QueueLine({ entry }: { entry: LogEntry }) {
  const parts = entry.message.startsWith('+ ')
    ? entry.message.slice(2).split('  ·  ')
    : null

  if (!parts || parts.length < 3) {
    return <LogLine entry={entry} />
  }

  const [title, category, pctRaw] = parts
  const pct = parseInt(pctRaw, 10)
  const scoreColor = pct >= 70 ? { bg: '#e8f5e9', fg: '#2e7d32' }
                   : pct >= 50 ? { bg: '#fff3e0', fg: '#e65100' }
                   : { bg: '#fce4ec', fg: '#c62828' }

  return (
    <div style={{
      display: 'flex', gap: 8, padding: '6px 10px',
      borderBottom: '1px solid #f0f0f0', alignItems: 'flex-start',
      background: '#fff',
    }}>
      <span style={{ color: '#bbb', flexShrink: 0, fontFamily: 'monospace', fontSize: 11, paddingTop: 2 }}>
        {entry.ts}
      </span>
      <span style={{
        fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 8,
        flexShrink: 0, background: scoreColor.bg, color: scoreColor.fg,
      }}>
        {pct}%
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: 600, color: '#1a1a1a',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {title}
        </div>
        {category && category !== 'General' && (
          <span style={{
            display: 'inline-block', marginTop: 2,
            fontSize: 10, color: '#555', background: '#f0f0f0',
            borderRadius: 4, padding: '1px 6px',
          }}>
            {category}
          </span>
        )}
      </div>
    </div>
  )
}

// ── panel ─────────────────────────────────────────────────────────────────────
interface PanelProps {
  title: string
  icon: string
  accent: string
  entries: LogEntry[]
  autoScroll: boolean
  renderLine?: (e: LogEntry) => React.ReactNode
}

function Panel({ title, icon, accent, entries, autoScroll, renderLine }: PanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [entries.length, autoScroll])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden',
      background: '#fafafa', minHeight: 0, height: '100%',
    }}>
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid #e5e7eb',
        background: '#fff', display: 'flex', alignItems: 'center', gap: 8,
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontWeight: 600, fontSize: 14, color: accent }}>{title}</span>
        <span style={{
          marginLeft: 'auto', background: '#f0f0f0', borderRadius: 10,
          fontSize: 11, padding: '1px 8px', color: '#666',
        }}>
          {entries.length} line{entries.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {entries.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#bbb', fontSize: 13 }}>
            No activity yet.
          </div>
        ) : (
          entries.map(e => renderLine ? renderLine(e) : <LogLine key={e.id} entry={e} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────
export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [live, setLive] = useState(true)
  const lastIdRef = useRef(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchLogs = useCallback(async () => {
    try {
      const fresh = await logsApi.get(lastIdRef.current)
      if (fresh.length > 0) {
        lastIdRef.current = fresh[fresh.length - 1].id
        setLogs(prev => {
          const combined = [...prev, ...fresh]
          return combined.length > MAX_ENTRIES
            ? combined.slice(combined.length - MAX_ENTRIES)
            : combined
        })
      }
    } catch {
      // silently skip
    }
  }, [])

  useEffect(() => {
    lastIdRef.current = 0
    fetchLogs()
  }, [fetchLogs])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (live) {
      intervalRef.current = setInterval(fetchLogs, POLL_MS)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [live, fetchLogs])

  const handleClear = async () => {
    await logsApi.clear()
    setLogs([])
    lastIdRef.current = 0
  }

  const scraperLogs = logs.filter(e => e.source === 'scraper' || e.source === 'scheduler' || e.source === 'email')
  const aiLogs     = logs.filter(e => e.source === 'ai')
  const queueLogs  = logs.filter(e => e.source === 'queue')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 'calc(100vh - 120px)' }}>
      {/* toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Live Activity Log</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: live ? '#22c55e' : '#d1d5db',
              boxShadow: live ? '0 0 0 2px #bbf7d0' : 'none',
            }} />
            <span style={{ fontSize: 12, color: '#666' }}>{live ? 'Live' : 'Paused'}</span>
          </div>
          <button
            onClick={() => setLive(v => !v)}
            style={{
              padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 6,
              background: live ? '#f0fdf4' : '#fff', cursor: 'pointer',
              fontSize: 12, color: live ? '#166534' : '#374151',
            }}
          >
            {live ? '⏸ Pause' : '▶ Resume'}
          </button>
          <button
            onClick={handleClear}
            style={{
              padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 6,
              background: '#fff', cursor: 'pointer', fontSize: 12, color: '#6b7280',
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* top row: Scraper + AI */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, flex: 1, minHeight: 0 }}>
        <Panel
          title="Scraper &amp; Scheduler"
          icon="🤖"
          accent="#1d4ed8"
          entries={scraperLogs}
          autoScroll={live}
        />
        <Panel
          title="AI Engine"
          icon="✦"
          accent="#7c3aed"
          entries={aiLogs}
          autoScroll={live}
        />
      </div>

      {/* bottom row: News Queue */}
      <div style={{ flex: '0 0 240px', minHeight: 0 }}>
        <Panel
          title="News Queue"
          icon="📥"
          accent="#059669"
          entries={queueLogs}
          autoScroll={live}
          renderLine={(e) => <QueueLine key={e.id} entry={e} />}
        />
      </div>

      <p style={{ fontSize: 11, color: '#aaa', margin: 0, flexShrink: 0 }}>
        Polling every {POLL_MS / 1000}s · last {MAX_ENTRIES.toLocaleString()} lines kept · only INFO and above shown
      </p>
    </div>
  )
}
