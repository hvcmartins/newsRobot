import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { TenantProvider } from './contexts/TenantContext'
import AppShell from './components/layout/AppShell'
import ArticlesPage from './pages/ArticlesPage'
import ArchivePage from './pages/ArchivePage'
import DashboardPage from './pages/DashboardPage'
import SourcesPage from './pages/SourcesPage'
import SourceLibraryPage from './pages/SourceLibraryPage'
import EmailPage from './pages/EmailPage'
import RunHistoryPage from './pages/RunHistoryPage'
import TenantSettingsPage from './pages/TenantSettingsPage'
import AISettingsPage from './pages/AISettingsPage'
import LogsPage from './pages/LogsPage'
import ScrapedUrlsPage from './pages/ScrapedUrlsPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <TenantProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="archive" element={<ArchivePage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="source-library" element={<SourceLibraryPage />} />
            <Route path="email" element={<EmailPage />} />
            <Route path="run-history" element={<RunHistoryPage />} />
            <Route path="settings" element={<TenantSettingsPage />} />
            <Route path="ai-settings" element={<AISettingsPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="seen-urls" element={<ScrapedUrlsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </TenantProvider>
    </BrowserRouter>
  )
}
