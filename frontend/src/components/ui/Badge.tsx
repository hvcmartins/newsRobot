import React from 'react'

type Variant = 'success' | 'error' | 'warning' | 'info' | 'neutral'

const colors: Record<Variant, { bg: string; color: string }> = {
  success: { bg: '#e8f5e9', color: '#2e7d32' },
  error:   { bg: '#ffebee', color: '#c62828' },
  warning: { bg: '#fff8e1', color: '#f57f17' },
  info:    { bg: '#e3f2fd', color: '#1565c0' },
  neutral: { bg: '#f0f2f5', color: '#555' },
}

interface BadgeProps {
  variant?: Variant
  children: React.ReactNode
}

export default function Badge({ variant = 'neutral', children }: BadgeProps) {
  const { bg, color } = colors[variant]
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 10,
      fontSize: 11,
      fontWeight: 600,
      background: bg,
      color,
    }}>
      {children}
    </span>
  )
}
