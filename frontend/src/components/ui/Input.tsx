import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export default function Input({ label, error, style, ...rest }: InputProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && <label style={{ fontSize: 12, fontWeight: 500, color: '#555' }}>{label}</label>}
      <input
        {...rest}
        style={{
          padding: '7px 10px',
          border: `1px solid ${error ? '#e53935' : '#ddd'}`,
          borderRadius: 6,
          outline: 'none',
          background: '#fff',
          transition: 'border-color 0.15s',
          ...style,
        }}
      />
      {error && <span style={{ fontSize: 11, color: '#e53935' }}>{error}</span>}
    </div>
  )
}
