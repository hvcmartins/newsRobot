import React, { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { aiConfigApi, type AIConfigUpdate } from '@/api/aiConfig'
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
    models: ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
    defaultModel: 'gemini-2.0-flash',
  },
  {
    value: 'ollama',
    label: 'Ollama (local)',
    description: 'Run AI locally on your Unraid server — no API key needed',
    requiresKey: false,
    requiresUrl: true,
    keyLabel: '',
    keyPlaceholder: '',
    keyDocsUrl: '',
    models: [],
    defaultModel: 'llama3.2',
  },
]

export default function AISettingsPage() {
  const { data: current, isLoading } = useQuery({
    queryKey: ['ai-config'],
    queryFn: aiConfigApi.get,
  })

  const [enabled, setEnabled] = useState(false)
  const [provider, setProvider] = useState('none')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [saved, setSaved] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    if (!current) return
    setEnabled(current.is_enabled)
    setProvider(current.provider)
    setModel(current.model ?? '')
    setBaseUrl(current.base_url ?? '')
    setApiKey('')  // never pre-fill the key for security
  }, [current])

  const def = PROVIDERS.find(p => p.value === provider) ?? PROVIDERS[0]

  const onProviderChange = (v: string) => {
    setProvider(v)
    setApiKey('')
    const d = PROVIDERS.find(p => p.value === v)
    if (d) setModel(d.defaultModel)
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload: AIConfigUpdate = {
        is_enabled: enabled,
        provider,
        model: model || def.defaultModel || null,
        base_url: baseUrl || null,
      }
      // Only send api_key if the user typed something
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      return aiConfigApi.update(payload)
    },
    onSuccess: () => {
      setSaved(true)
      setApiKey('')
      setTimeout(() => setSaved(false), 3000)
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
                label="Ollama Base URL"
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                placeholder="http://192.168.1.100:11434"
              />
              <p style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                Use your Unraid server IP if Ollama runs as a container on the same machine.
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
