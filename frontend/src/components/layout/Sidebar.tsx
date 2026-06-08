import React from 'react'
import { NavLink } from 'react-router-dom'
import { useTenant } from '@/contexts/TenantContext'
import { useQuery } from '@tanstack/react-query'
import { articleApi } from '@/api/articles'

const nav = [
  { to: '/dashboard',     label: 'Dashboard',      icon: '📊' },
  { to: '/articles',      label: 'News Queue',     icon: '📰' },
  { to: '/archive',       label: 'Archive',        icon: '🗂' },
  { to: '/sources',       label: 'My Sources',     icon: '🔗' },
  { to: '/source-library', label: 'Source Library', icon: '📚' },
  { to: '/email',         label: 'Email',          icon: '✉️' },
  { to: '/run-history',   label: 'Run History',    icon: '🔁' },
  { to: '/seen-urls',     label: 'Seen URLs',      icon: '🔍' },
  { to: '/logs',          label: 'Activity Log',   icon: '📡' },
  { to: '/ai-settings',   label: 'AI Settings',    icon: '✦' },
  { to: '/settings',      label: 'Settings',       icon: '⚙️' },
]

export default function Sidebar() {
  const { activeTenant } = useTenant()

  const { data } = useQuery({
    queryKey: ['articles', 'queue-count', activeTenant?.id],
    queryFn: () =>
      activeTenant
        ? articleApi.list({ tenant_id: activeTenant.id, size: 1 })
        : null,
    enabled: !!activeTenant,
    refetchInterval: 60_000,
  })

  const queueCount = data?.total ?? 0

  return (
    <nav style={{
      width: 'var(--sidebar-width)', flexShrink: 0,
      background: '#fff', borderRight: '1px solid #eee',
      display: 'flex', flexDirection: 'column',
      paddingTop: 8,
    }}>
      {nav.map(({ to, label, icon }) => (
        <NavLink
          key={to}
          to={to}
          style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 16px', fontSize: 13, fontWeight: 500,
            color: isActive ? 'var(--brand-color)' : '#555',
            background: isActive ? 'var(--brand-color-light)' : 'transparent',
            borderLeft: isActive ? '3px solid var(--brand-color)' : '3px solid transparent',
            transition: 'background 0.15s',
            textDecoration: 'none',
          })}
        >
          <span style={{ fontSize: 16 }}>{icon}</span>
          <span style={{ flex: 1 }}>{label}</span>
          {to === '/articles' && queueCount > 0 && (
            <span style={{
              background: 'var(--brand-color)', color: '#fff',
              fontSize: 10, fontWeight: 700, padding: '1px 6px',
              borderRadius: 8, minWidth: 18, textAlign: 'center',
            }}>
              {queueCount > 99 ? '99+' : queueCount}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
