import React, { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiConfigApi, type AIConfigUpdate, type LocalModel } from '@/api/aiConfig'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

interface ProviderDef {
  value: string
  label: string
  description: string
  requiresKey: boolean
  requiresUrl: boolean
  keyLabel: string
  keyPlaceholder: string
  keyDocsUrl: string
  models: string[]
  defaultModel: string
}

const PROVIDERS: ProviderDef[] = [
  {
    value: 'none',
    label: 'None',
    description: 'AI disabled — keyword matching only',
    requiresKey: false,
    requiresUrl: false,
    keyLabel: '',
    keyPlaceholder: '',
    keyDocsUrl: '',
    models: [],
    defaultModel: '',
  },
  {
    value: 'claude',
    label: 'Claude',
    description: 'Anthropic\'s Claude — excellent reasoning and news analysis',
    requiresKey: true,
    requiresUrl: false,
    keyLabel: 'Anthropic API Key',
    keyPlaceholder: 'sk-ant-...',
    keyDocsUrl: 'https://console.anthropic.com/settings/keys',
    models: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8'],
    defaultModel: 'claude-haiku-4-5-20251001',
  },
  {
    value: 'openai',
    label: 'ChatGPT (OpenAI)',
    description: 'OpenAI GPT models — reliable and widely supported',
    requiresKey: true,
    requiresUrl: false,
    keyLabel: 'OpenAI API Key',
    keyPlaceholder: 'sk-...',
    keyDocsUrl: 'https://platform.openai.com/api-keys',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
    defaultModel: 'gpt-4o-mini',
  },
  {
    value: 'perplexity',
    label: 'Perplexity',
    description: 'Perplexity AI — great for news with web-aware models',
    requiresKey: true,
    requiresUrl: false,
    keyLabel: 'Perplexity API Key',
    keyPlaceholder: 'pplx-...',
    keyDocsUrl: 'https://www.perplexity.ai/settings/api',
    models: [
      'llama-3.1-sonar-small-128k-online',
      'llama-3.1-sonar-large-128k-online',
      'llama-3.1-sonar-huge-128k-online',
    ],
    defaultModel: 'llama-3.1-sonar-small-128k-online',
  },
  {
    value: 'gemini',
    label: 'Gemini (Google)',
    description: 'Google Gemini — fast and capable with a generous free tier',
    requiresKey: true,
    requiresUrl: false,
    keyLabel: 'Google AI API Key',
    keyPlaceholder: 'AIza...',
    keyDocsUrl: 'https://aistudio.google.com/app/apikey',
    models: ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
    defaultModel: 'gemini-2.5-flash',
  },
  {
    value: 'ollama',
    label: 'Ollama (local)',
    description: 'Connect to a separate Ollama server — no API key needed',
    requiresKey: false,
    requiresUrl: true,
    keyLabel: '',
    keyPlaceholder: '',
    keyDocsUrl: '',
    models: [],
    defaultModel: 'llama3.2',
  },
  {
    value: 'llamaserver',
    label: 'LLM Server (local)',
    description: 'llama.cpp server, LM Studio, vLLM — any OpenAI-compatible local server',
    requiresKey: false,
    requiresUrl: true,
    keyLabel: '',
    keyPlaceholder: '',
    keyDocsUrl: '',
    models: [],
    defaultModel: '',
  },
  {
    value: 'llamacpp',
    label: 'Local AI (built-in)',
    description: 'Download & run models directly in this container — CPU only, no server needed',
    requiresKey: false,
    requiresUrl: false,
    keyLabel: '',
    keyPlaceholder: '',
    keyDocsUrl: '',
    models: [],
    defaultModel: '',
  },
]

export default function AISettingsPage() {
  const qc = useQueryClient()

  const { data: current, isLoading } = useQuery({
    queryKey: ['ai-config'],
    queryFn: aiConfigApi.get,
  })

  const { data: localModels, refetch: refetchModels } = useQuery({
    queryKey: ['ai-local-models'],
    queryFn: aiConfigApi.listLocalModels,
    refetchInterval: (query) => {
      const models = query.state.data
      if (models?.some(m => m.status === 'downloading')) return 2000
      return false
    },
  })

  const [enabled, setEnabled] = useState(false)
  const [provider, setProvider] = useState('none')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [localModelId, setLocalModelId] = useState('')
  const [cpuLimit, setCpuLimit] = useState(80)
  const [nGpuLayers, setNGpuLayers] = useState(-1)
  const [serperKey, setSerperKey] = useState('')
  const [googleKey, setGoogleKey] = useState('')
  const [googleCx, setGoogleCx] = useState('')
  const [relevanceThreshold, setRelevanceThreshold] = useState(0.3)
  const [saved, setSaved] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    if (!current) return
    setEnabled(current.is_enabled)
    setProvider(current.provider)
    setModel(current.model ?? '')
    setBaseUrl(current.base_url ?? '')
    setLocalModelId(current.local_model_id ?? '')
    setCpuLimit(current.cpu_limit_percent ?? 80)
    setNGpuLayers(current.n_gpu_layers ?? -1)
    setGoogleCx(current.google_search_cx ?? '')
    setRelevanceThreshold(current.relevance_threshold ?? 0.3)
    setApiKey('')
    setSerperKey('')
    setGoogleKey('')
  }, [current])

  const def = PROVIDERS.find(p => p.value === provider) ?? PROVIDERS[0]

  const onProviderChange = (v: string) => {
    setProvider(v)
    setApiKey('')
    const d = PROVIDERS.find(p => p.value === v)
    if (d) setModel(d.defaultModel)
    // Auto-enable when a real provider is picked; auto-disable for "none"
    if (v === 'none') setEnabled(false)
    else setEnabled(true)
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload: AIConfigUpdate = {
        is_enabled: enabled,
        provider,
        model: model || def.defaultModel || null,
        base_url: baseUrl || null,
        local_model_id: provider === 'llamacpp' ? (localModelId || null) : null,
        cpu_limit_percent: provider === 'llamacpp' ? cpuLimit : undefined,
        n_gpu_layers: provider === 'llamacpp' ? nGpuLayers : undefined,
        google_search_cx: googleCx.trim() || null,
        relevance_threshold: relevanceThreshold,
      }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      if (serperKey.trim()) payload.serper_api_key = serperKey.trim()
      if (googleKey.trim()) payload.google_search_api_key = googleKey.trim()
      return aiConfigApi.update(payload)
    },
    onSuccess: () => {
      setSaved(true)
      setApiKey('')
      qc.invalidateQueries({ queryKey: ['ai-config'] })
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const downloadMut = useMutation({
    mutationFn: (modelId: string) => aiConfigApi.downloadLocalModel(modelId),
    onSuccess: () => refetchModels(),
  })

  const deleteMut = useMutation({
    mutationFn: (modelId: string) => aiConfigApi.deleteLocalModel(modelId),
    onSuccess: () => {
      refetchModels()
      if (localModelId === deleteMut.variables) setLocalModelId('')
    },
  })

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await aiConfigApi.test()
      setTestResult({ ok: r.ok, message: r.ok ? r.response ?? 'OK' : r.error ?? 'Failed' })
    } catch {
      setTestResult({ ok: false, message: 'Request failed' })
    } finally {
      setTesting(false)
    }
  }

  if (isLoading) return <p style={{ padding: 24 }}>Loading…</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 640 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>AI Settings</h1>

      <p style={{ fontSize: 13, color: '#666', marginTop: -16 }}>
        AI enriches articles with smart summaries, relevance scoring, and category detection.
        Without AI, the robot uses keyword matching instead.
      </p>

      {/* Enable toggle */}
      <section style={card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Enable AI</h2>
            <p style={{ fontSize: 12, color: '#888' }}>
              {enabled ? 'AI is active — articles will be enriched after scraping' : 'AI is off — using keyword matching only'}
            </p>
          </div>
          <label style={{ position: 'relative', display: 'inline-block', width: 44, height: 24, flexShrink: 0 }}>
            <input
              type="checkbox"
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
              style={{ opacity: 0, width: 0, height: 0 }}
            />
            <span style={{
              position: 'absolute', inset: 0, borderRadius: 24, cursor: 'pointer',
              background: enabled ? 'var(--brand-color)' : '#ccc',
              transition: 'background 0.2s',
            }}>
              <span style={{
                position: 'absolute', top: 3, left: enabled ? 23 : 3, width: 18, height: 18,
                background: '#fff', borderRadius: '50%', transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              }} />
            </span>
          </label>
        </div>
      </section>

      {/* Provider selection */}
      <section style={card}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>AI Provider</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {PROVIDERS.map(p => (
            <button
              key={p.value}
              onClick={() => onProviderChange(p.value)}
              style={{
                textAlign: 'left', padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                border: provider === p.value ? '2px solid var(--brand-color)' : '2px solid #e5e7eb',
                background: provider === p.value ? 'var(--brand-color-light)' : '#fff',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: provider === p.value ? 'var(--brand-color)' : '#222' }}>
                {p.label}
              </div>
              <div style={{ fontSize: 11, color: '#777', marginTop: 3, lineHeight: 1.4 }}>
                {p.description}
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* Provider config */}
      {provider !== 'none' && (
        <section style={card}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Configuration</h2>

          {def.requiresKey && (
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>{def.keyLabel}</label>
              <input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={current?.api_key_set ? '••••••••  (leave blank to keep current)' : def.keyPlaceholder}
                style={inputStyle}
              />
              {current?.api_key_set && !apiKey && (
                <p style={{ fontSize: 11, color: '#2e7d32', marginTop: 4 }}>✓ API key is set</p>
              )}
              {def.keyDocsUrl && (
                <p style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                  Get your key at{' '}
                  <a href={def.keyDocsUrl} target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--brand-color)' }}>
                    {def.keyDocsUrl.replace('https://', '')}
                  </a>
                </p>
              )}
            </div>
          )}

          {def.requiresUrl && (
            <div style={{ marginBottom: 16 }}>
              <Input
                label={provider === 'llamaserver' ? 'Server Base URL (include /v1)' : 'Ollama Base URL'}
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                placeholder={provider === 'llamaserver'
                  ? 'http://192.168.2.166:8081/v1'
                  : 'http://192.168.1.100:11434'}
              />
              <p style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                {provider === 'llamaserver'
                  ? 'Include /v1 at the end. Works with llama.cpp server, LM Studio, vLLM, Jan, and any OpenAI-compatible server.'
                  : 'Use your Unraid server IP if Ollama runs as a container on the same machine.'}
              </p>
            </div>
          )}

          {provider === 'llamacpp' && (
            <LocalModelPicker
              models={localModels ?? []}
              selectedId={localModelId}
              onSelect={setLocalModelId}
              onDownload={id => downloadMut.mutate(id)}
              onDelete={id => deleteMut.mutate(id)}
            />
          )}

          {provider === 'llamacpp' && (
            <div style={{ marginTop: 16 }}>
              <label style={labelStyle}>
                CPU Usage Limit — {cpuLimit}%
                {' '}
                <span style={{ fontWeight: 400, color: '#999' }}>
                  ({Math.max(1, Math.round((navigator.hardwareConcurrency || 4) * cpuLimit / 100))} of {navigator.hardwareConcurrency || 4} threads)
                </span>
              </label>
              <input
                type="range"
                min={25}
                max={100}
                step={5}
                value={cpuLimit}
                onChange={e => setCpuLimit(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--brand-color)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#999', marginTop: 2 }}>
                <span>25% (slower, keeps system responsive)</span>
                <span>100% (fastest)</span>
              </div>
            </div>
          )}

          {provider === 'llamacpp' && (
            <div style={{ marginTop: 16 }}>
              <label style={labelStyle}>GPU Layers</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <input
                  type="number" min={-1}
                  value={nGpuLayers}
                  onChange={e => setNGpuLayers(parseInt(e.target.value) || -1)}
                  style={{ width: 80, padding: '7px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}
                />
                <span style={{ fontSize: 12, color: '#888' }}>
                  {nGpuLayers === -1 ? 'All layers offloaded to GPU (recommended if GPU available)' :
                   nGpuLayers === 0 ? 'CPU only — no GPU offloading' :
                   `${nGpuLayers} layers on GPU, rest on CPU`}
                </span>
              </div>
              <p style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                -1 = offload all layers. 0 = CPU only. Requires ROCm (AMD) or CUDA (NVIDIA) build.
              </p>
            </div>
          )}

          <div>
            <label style={labelStyle}>Model</label>
            {def.models.length > 0 ? (
              <select
                value={model}
                onChange={e => setModel(e.target.value)}
                style={{ ...inputStyle, background: '#fff' }}
              >
                {def.models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <Input
                label=""
                value={model}
                onChange={e => setModel(e.target.value)}
                placeholder={def.defaultModel || 'e.g. llama3.2'}
              />
            )}
          </div>
        </section>
      )}

      {/* Web Search for Source Discovery */}
      <section style={card}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Web Search for Source Discovery</h2>
        <p style={{ fontSize: 12, color: '#888', marginBottom: 14, lineHeight: 1.5 }}>
          When discovering sources the AI suggests feeds from memory — URLs are often invented.
          A web search API finds <em>real, live</em> feeds instead.
          Without a key, DuckDuckGo is used as a free fallback.
        </p>

        {/* Serper — recommended */}
        <div style={{ background: '#f0fdf4', border: '1.5px solid #bbf7d0', borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Serper.dev</span>
            <span style={{ fontSize: 10, background: '#4caf50', color: '#fff', borderRadius: 10, padding: '1px 8px', fontWeight: 700 }}>RECOMMENDED</span>
            {current?.serper_api_key_set && <span style={{ fontSize: 11, color: '#4caf50' }}>✓ configured</span>}
          </div>
          <p style={{ fontSize: 12, color: '#555', marginBottom: 8, lineHeight: 1.4 }}>
            Google Search results via a simple API. No Programmable Search Engine needed — just one key.{' '}
            2,500 free queries/month.{' '}
            <a href="https://serper.dev" target="_blank" rel="noreferrer" style={{ color: '#1677ff' }}>Sign up at serper.dev</a>
            {' '}→ copy your API key.
          </p>
          <Input label="" value={serperKey} onChange={e => setSerperKey(e.target.value)}
            placeholder={current?.serper_api_key_set ? '••••••••  (leave blank to keep)' : 'Serper.dev API key'}
            type="password" />
        </div>

        {/* Google Custom Search — legacy */}
        <details style={{ fontSize: 12 }}>
          <summary style={{ cursor: 'pointer', color: '#888', marginBottom: 8 }}>
            Google Custom Search (legacy — only works with engines created before Jan 2025)
            {current?.google_search_api_key_set && <span style={{ color: '#4caf50', marginLeft: 6 }}>✓ set</span>}
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
            <Input label="Google API Key" value={googleKey} onChange={e => setGoogleKey(e.target.value)}
              placeholder={current?.google_search_api_key_set ? '••••••••  (leave blank to keep)' : 'AIza...'}
              type="password" />
            <Input label="Search Engine ID (cx)" value={googleCx} onChange={e => setGoogleCx(e.target.value)}
              placeholder={current?.google_search_cx ?? 'e.g. 123456789:xyz'} />
          </div>
        </details>
      </section>

      {/* Relevance Threshold */}
      <section style={card}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Article Relevance Filter</h2>
        <p style={{ fontSize: 12, color: '#888', marginBottom: 14, lineHeight: 1.5 }}>
          After AI enrichment, articles scored below this threshold are <strong>permanently deleted</strong> from the queue.
          Lower values keep more articles (less aggressive filtering). Default is 0.3.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <input
            type="range"
            min={0}
            max={0.9}
            step={0.05}
            value={relevanceThreshold}
            onChange={e => setRelevanceThreshold(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: 'var(--brand-color)' }}
          />
          <span style={{
            minWidth: 40, textAlign: 'center', fontSize: 14, fontWeight: 600,
            color: relevanceThreshold >= 0.6 ? '#c62828' : relevanceThreshold >= 0.4 ? '#e65100' : '#2e7d32',
          }}>
            {relevanceThreshold.toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#aaa', marginTop: 4 }}>
          <span>0.00 — keep everything</span>
          <span>0.90 — very strict</span>
        </div>
      </section>

      {/* Test */}
      {provider !== 'none' && (
        <section style={card}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Test Connection</h2>
          <p style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>
            Sends a sample article to the AI and checks that it responds correctly. Save first.
          </p>
          <Button variant="secondary" loading={testing} onClick={handleTest}>
            Test AI Connection
          </Button>
          {testResult && (
            <div style={{
              marginTop: 12, padding: '10px 14px', borderRadius: 6, fontSize: 12,
              background: testResult.ok ? '#e8f5e9' : '#ffebee',
              color: testResult.ok ? '#2e7d32' : '#c62828',
              border: `1px solid ${testResult.ok ? '#a5d6a7' : '#ef9a9a'}`,
              lineHeight: 1.5,
            }}>
              {testResult.ok ? '✓ ' : '✗ '}{testResult.message}
            </div>
          )}
        </section>
      )}

      {saved && (
        <p style={{ fontSize: 13, color: '#2e7d32', background: '#e8f5e9', padding: '8px 12px', borderRadius: 6 }}>
          AI settings saved!
        </p>
      )}
      {saveMut.isError && (
        <p style={{ fontSize: 12, color: '#e53935' }}>
          {(saveMut.error as Error).message}
        </p>
      )}

      <Button loading={saveMut.isPending} onClick={() => saveMut.mutate()}>
        Save AI Settings
      </Button>
    </div>
  )
}

// ── Local model picker ────────────────────────────────────────────────────────

function LocalModelPicker({ models, selectedId, onSelect, onDownload, onDelete }: {
  models: LocalModel[]
  selectedId: string
  onSelect: (id: string) => void
  onDownload: (id: string) => void
  onDelete: (id: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>
        Choose a model to download and use
      </label>
      <p style={{ fontSize: 11, color: '#888', marginTop: -6 }}>
        Models are stored in <code style={{ background: '#f5f5f5', padding: '1px 4px', borderRadius: 3 }}>/data/models/</code> and survive container restarts.
      </p>
      {models.map(m => {
        const isSelected = selectedId === m.id
        const isReady = m.status === 'ready'
        const isDownloading = m.status === 'downloading'
        return (
          <div key={m.id} style={{
            border: isSelected ? '2px solid var(--brand-color)' : '1px solid #e5e7eb',
            borderRadius: 8, padding: '12px 14px',
            background: isSelected ? 'var(--brand-color-light)' : '#fafafa',
            cursor: isReady ? 'pointer' : 'default',
          }} onClick={() => isReady && onSelect(m.id)}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  {isReady && (
                    <input type="radio" readOnly checked={isSelected}
                      style={{ accentColor: 'var(--brand-color)' }} />
                  )}
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{m.name}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 10,
                    background: m.tag === 'Recommended' ? '#e8f5e9' : m.tag === 'Lite' ? '#e3f2fd' : '#fff3e0',
                    color: m.tag === 'Recommended' ? '#2e7d32' : m.tag === 'Lite' ? '#1565c0' : '#e65100',
                  }}>{m.tag}</span>
                </div>
                <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>{m.description}</div>
                <div style={{ fontSize: 11, color: '#999' }}>
                  {m.size_gb} GB download · {m.ram_gb} GB RAM needed
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                {isReady ? (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <span style={{ fontSize: 11, color: '#2e7d32', fontWeight: 600 }}>✓ Ready</span>
                    <button onClick={e => { e.stopPropagation(); onDelete(m.id) }}
                      style={{ fontSize: 10, color: '#e53935', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                      Remove
                    </button>
                  </div>
                ) : isDownloading ? (
                  <span style={{ fontSize: 11, color: '#1565c0' }}>Downloading…</span>
                ) : (
                  <button onClick={e => { e.stopPropagation(); onDownload(m.id) }}
                    style={{
                      fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 6,
                      background: 'var(--brand-color)', color: '#fff', border: 'none', cursor: 'pointer',
                    }}>
                    Download
                  </button>
                )}
                {m.status === 'error' && (
                  <span style={{ fontSize: 10, color: '#e53935' }}>{m.error}</span>
                )}
              </div>
            </div>
            {isDownloading && (
              <div style={{ marginTop: 8, background: '#e0e0e0', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 4,
                  background: 'var(--brand-color)',
                  width: `${m.progress}%`,
                  transition: 'width 0.5s ease',
                }} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

const card: React.CSSProperties = {
  background: '#fff', borderRadius: 10, padding: 24,
  boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
  display: 'flex', flexDirection: 'column',
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: '#555', marginBottom: 6,
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', border: '1px solid #ddd',
  borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
}
