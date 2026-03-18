import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Map, LineChart, Briefcase,
  ClipboardCheck, FlaskConical, Settings, LogOut,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth'

const NAV = [
  { to: '/overview', label: '态势总览', icon: LayoutDashboard },
  { to: '/nesting-map', label: '区间套地图', icon: Map },
  { to: '/chart/AAPL', label: '缠论图表', icon: LineChart },
  { to: '/positions', label: '持仓管理', icon: Briefcase },
  { to: '/review', label: '信号回顾', icon: ClipboardCheck },
  { to: '/backtest', label: '回测实验', icon: FlaskConical },
  { to: '/settings', label: '设置', icon: Settings },
]

export default function Sidebar() {
  const { username, logout } = useAuthStore()

  return (
    <aside className="w-52 h-screen sticky top-0 flex flex-col border-r border-bg-border bg-bg-card/50 shrink-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-bg-border">
        <div className="text-accent-cyan text-sm font-bold tracking-[3px]">ZEN</div>
        <div className="text-text-muted text-[10px] tracking-[2px] mt-0.5">ALPHA TERMINAL</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-[11px] tracking-wide transition-colors ${
                isActive
                  ? 'text-accent-cyan bg-accent-cyan/5 border-r-2 border-accent-cyan'
                  : 'text-text-dim hover:text-text-primary hover:bg-bg-hover'
              }`
            }
          >
            <Icon size={14} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-3 border-t border-bg-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] text-text-primary">{username || 'OPERATOR'}</div>
            <div className="text-[9px] text-text-muted tracking-wider">ACTIVE</div>
          </div>
          <button
            onClick={() => { logout(); window.location.href = '/login' }}
            className="p-1.5 rounded hover:bg-accent-red/10 text-text-muted hover:text-accent-red transition-colors"
            title="Logout"
          >
            <LogOut size={13} />
          </button>
        </div>
      </div>
    </aside>
  )
}
