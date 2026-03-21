import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import OverviewPage from '@/pages/OverviewPage'
import SignalAnalysisPage from '@/pages/SignalAnalysisPage'
import StrategyPage from '@/pages/StrategyPage'
import WatchlistPage from '@/pages/WatchlistPage'
import NotificationsPage from '@/pages/NotificationsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppLayout />}>
          {/* Section 1: Overview */}
          <Route path="/overview" element={<OverviewPage />} />

          {/* Section 2: Signal Analysis */}
          <Route path="/analysis" element={<SignalAnalysisPage />} />
          <Route path="/strategy" element={<StrategyPage />} />

          {/* Section 3: Settings */}
          <Route path="/settings/watchlist" element={<WatchlistPage />} />
          <Route path="/settings/notifications" element={<NotificationsPage />} />

          {/* Redirects */}
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/settings" element={<Navigate to="/settings/watchlist" replace />} />

          {/* Legacy redirects */}
          <Route path="/nesting-map" element={<Navigate to="/analysis" replace />} />
          <Route path="/nesting-map/:symbol" element={<Navigate to="/analysis" replace />} />
          <Route path="/chart/:symbol" element={<Navigate to="/analysis" replace />} />
          <Route path="/pipeline" element={<Navigate to="/overview" replace />} />
          <Route path="/review" element={<Navigate to="/overview" replace />} />
          <Route path="/positions" element={<Navigate to="/overview" replace />} />
          <Route path="/backtest" element={<Navigate to="/strategy" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
