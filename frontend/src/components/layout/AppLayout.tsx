import { Outlet, Navigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useAuthStore } from '@/stores/auth'

export default function AppLayout() {
  const token = useAuthStore((s) => s.token)

  if (!token) return <Navigate to="/login" replace />

  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="w-full max-w-[1400px] mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
