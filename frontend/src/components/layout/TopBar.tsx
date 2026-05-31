import React from 'react'
import TenantSwitcher from './TenantSwitcher'

export default function TopBar() {
  return (
    <header style={{
      height: 'var(--topbar-height)', background: 'var(--brand-color)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 20px', position: 'sticky', top: 0, zIndex: 100,
      boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 20 }}>🤖</span>
        <span style={{ color: '#fff', fontWeight: 700, fontSize: 16, letterSpacing: '-0.3px' }}>
          NewsRobot
        </span>
      </div>
      <TenantSwitcher />
    </header>
  )
}
