import React, { useState } from 'react'
import { useTenant } from '@/contexts/TenantContext'
import type { Tenant } from '@/api/types'

export default function TenantSwitcher() {
  const { tenants, activeTenant, setActiveTenant } = useTenant()
  const [open, setOpen] = useState(false)

  if (!activeTenant) return null

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px', background: 'rgba(255,255,255,0.15)',
          border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6,
          color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 500,
        }}
      >
        <span
          style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff', flexShrink: 0 }}
        />
        {activeTenant.name}
        <span style={{ fontSize: 10, opacity: 0.8 }}>▼</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, background: '#fff',
          border: '1px solid #eee', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          minWidth: 180, zIndex: 200, overflow: 'hidden',
        }}>
          {tenants.map((t: Tenant) => (
            <button
              key={t.id}
              onClick={() => { setActiveTenant(t); setOpen(false) }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                width: '100%', padding: '10px 14px', background: 'none',
                border: 'none', cursor: 'pointer', fontSize: 13,
                fontWeight: t.slug === activeTenant.slug ? 600 : 400,
                color: t.slug === activeTenant.slug ? 'var(--brand-color)' : '#333',
                textAlign: 'left',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.primary_color, flexShrink: 0 }} />
              {t.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
