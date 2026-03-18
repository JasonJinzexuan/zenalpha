import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import OverviewPage from '@/pages/OverviewPage'
import NestingMapPage from '@/pages/NestingMapPage'
import ChartPage from '@/pages/ChartPage'
import PositionsPage from '@/pages/PositionsPage'
import ReviewPage from '@/pages/ReviewPage'
import BacktestPage from '@/pages/BacktestPage'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppLayout />}>
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/nesting-map" element={<NestingMapPage />} />
          <Route path="/nesting-map/:symbol" element={<NestingMapPage />} />
          <Route path="/chart/:symbol" element={<ChartPage />} />
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
