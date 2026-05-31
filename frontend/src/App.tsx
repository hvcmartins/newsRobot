import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { TenantProvider } from './contexts/TenantContext'
import AppShell from './components/layout/AppShell'
import ArticlesPage from './pages/ArticlesPage'
import SourcesPage from './pages/SourcesPage'
import SourceLibraryPage from './pages/SourceLibraryPage'
import EmailPage from './pages/EmailPage'
import RunHistoryPage from './pages/RunHistoryPage'
import TenantSettingsPage from './pages/TenantSettingsPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <TenantProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/articles" replace />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="source-library" element={<SourceLibraryPage />} />
            <Route path="email" element={<EmailPage />} />
            <Route path="run-history" element={<RunHistoryPage />} />
            <Route path="settings" element={<TenantSettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </TenantProvider>
    </BrowserRouter>
  )
}
