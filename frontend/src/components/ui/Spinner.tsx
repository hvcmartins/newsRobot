import React from 'react'

export default function Spinner({ size = 24 }: { size?: number }) {
  return (
    <span style={{
      display: 'inline-block',
      width: size,
      height: size,
      border: `2px solid var(--brand-color)`,
      borderTopColor: 'transparent',
      borderRadius: '50%',
      animation: 'spin 0.6s linear infinite',
    }} />
  )
}
