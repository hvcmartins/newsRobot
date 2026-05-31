import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md'
  loading?: boolean
}

const styles: Record<string, React.CSSProperties> = {
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    border: 'none',
    borderRadius: 6,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'opacity 0.15s, background 0.15s',
    whiteSpace: 'nowrap',
  },
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading,
  disabled,
  children,
  style,
  ...rest
}: ButtonProps) {
  const pad = size === 'sm' ? '5px 10px' : '8px 16px'
  const fontSize = size === 'sm' ? 12 : 13

  const bg =
    variant === 'primary'
      ? 'var(--brand-color)'
      : variant === 'danger'
      ? '#e53935'
      : variant === 'ghost'
      ? 'transparent'
      : '#f0f2f5'

  const color =
    variant === 'primary' || variant === 'danger' ? '#fff' : '#333'
  const border = variant === 'secondary' ? '1px solid #ddd' : 'none'

  return (
    <button
      {...rest}
      disabled={disabled || loading}
      style={{
        ...styles.base,
        padding: pad,
        fontSize,
        background: bg,
        color,
        border,
        opacity: disabled || loading ? 0.6 : 1,
        ...style,
      }}
    >
      {loading && <span style={{ width: 12, height: 12, border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.6s linear infinite' }} />}
      {children}
    </button>
  )
}
