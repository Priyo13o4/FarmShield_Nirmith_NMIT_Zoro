import { I18nextProvider, useTranslation } from 'react-i18next'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { isDemoMode } from './config/runtime'
import AppLayout from './components/layout/AppLayout'
import { FarmProvider } from './context/FarmContext'
import i18n from './i18n'
import Alerts from './pages/Alerts'
import Controls from './pages/Controls'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Settings from './pages/Settings'
import Chat from './pages/Chat'

function AppRoutes() {
  const { t } = useTranslation()
  const location = useLocation()

  const showSetupBanner = !isDemoMode && !localStorage.getItem('fs_api_url')

  const needsRedirect = showSetupBanner && location.pathname !== '/settings'

  if (needsRedirect) {
    return <Navigate to="/settings" replace />
  }

  return (
    <Routes>
      <Route
        element={
          <AppLayout
            showSetupBanner={showSetupBanner}
            setupBannerText={t('app.setupBanner')}
          />
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="history" element={<History />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="chat" element={<Chat />} />
        <Route path="controls" element={<Controls />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <FarmProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </FarmProvider>
    </I18nextProvider>
  )
}
