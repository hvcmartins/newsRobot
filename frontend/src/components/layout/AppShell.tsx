import React from 'react'
import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import Sidebar from './Sidebar'

export default function AppShell() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopBar />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{ flex: 1, overflow: 'auto', padding: 24 }}>
          <Outlet />
        </main>
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        --brand-color-light { color-mix(in srgb, var(--brand-color) 12%, white); }
      `}</style>
    </div>
  )
}
