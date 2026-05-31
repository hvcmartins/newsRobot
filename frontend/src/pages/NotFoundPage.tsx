import React from 'react'
import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div style={{ textAlign: 'center', padding: 80, color: '#999' }}>
      <div style={{ fontSize: 64, marginBottom: 16 }}>404</div>
      <p style={{ marginBottom: 16 }}>Page not found.</p>
      <Link to="/articles" style={{ color: 'var(--brand-color)', fontSize: 14 }}>← Back to Articles</Link>
    </div>
  )
}
