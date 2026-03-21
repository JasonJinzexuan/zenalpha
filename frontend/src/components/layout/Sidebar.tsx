import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, LineChart, Sliders, ChevronDown,
  Settings, LogOut, List, Bell, Target, FlaskConical,
  Menu, X,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/cn'

interface NavSection {
  label: string
  icon: typeof LayoutDashboard
  children: { to: string; label: string; icon: typeof LayoutDashboard }[]
}

const SECTIONS: NavSection[] = [
  {
    label: '态势总览',
    icon: LayoutDashboard,
    children: [
      { to: '/overview', label: '总览面板', icon: LayoutDashboard },
    ],
  },
  {
    label: '信号分析',
    icon: LineChart,
    children: [
      { to: '/analysis', label: '标的分析', icon: Target },
      { to: '/strategy', label: '策略优化', icon: FlaskConical },
    ],
  },
  {
    label: '设置',
    icon: Settings,
    children: [
      { to: '/settings/watchlist', label: 'Watchlist 管理', icon: List },
      { to: '/settings/notifications', label: '通知配置', icon: Bell },
    ],
  },
]

export default function Sidebar() {
  const { username, logout } = useAuthStore()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({})
  const [mobileOpen, setMobileOpen] = useState(false)

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Close on escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const toggle = (idx: number) =>
    setCollapsed(prev => ({ ...prev, [idx]: !prev[idx] }))

  const isInSection = (section: NavSection) =>
    section.children.some(c => location.pathname.startsWith(c.to))

  const navContent = (
    <>
      {/* Logo */}
      <div className="px-4 py-5 border-b border-bg-border flex items-center justify-between">
        <div>
          <div className="text-accent-cyan text-sm font-bold tracking-[3px]">ZEN</div>
          <div className="text-text-muted text-[10px] tracking-[2px] mt-0.5">ALPHA TERMINAL</div>
        </div>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="md:hidden p-1.5 rounded hover:bg-bg-hover text-text-muted"
        >
          <X size={16} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {SECTIONS.map((section, idx) => {
          const isOpen = collapsed[idx] !== true || isInSection(section)
          const SectionIcon = section.icon

          return (
            <div key={idx} className="mb-1">
              <button
                onClick={() => toggle(idx)}
                className="w-full flex items-center justify-between px-4 py-2 text-[10px] tracking-wider text-text-muted hover:text-text-primary transition-colors"
              >
                <span className="flex items-center gap-2 font-semibold uppercase">
                  <SectionIcon size={12} />
                  {section.label}
                </span>
                <ChevronDown
                  size={11}
                  className={cn('transition-transform', isOpen && 'rotate-180')}
                />
              </button>

              {isOpen && (
                <div className="space-y-0.5">
                  {section.children.map(({ to, label, icon: Icon }) => (
                    <NavLink
                      key={to}
                      to={to}
                      className={({ isActive }) =>
                        `flex items-center gap-3 pl-8 pr-4 py-2 text-[11px] tracking-wide transition-colors ${
                          isActive
                            ? 'text-accent-cyan bg-accent-cyan/5 border-r-2 border-accent-cyan'
                            : 'text-text-dim hover:text-text-primary hover:bg-bg-hover'
                        }`
                      }
                    >
                      <Icon size={13} />
                      {label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          )
        })}
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
    </>
  )

  return (
    <>
      {/* Mobile hamburger button — fixed top-left */}
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 p-2 rounded-lg bg-bg-card border border-bg-border text-text-muted hover:text-text-primary transition-colors"
        aria-label="Open menu"
      >
        <Menu size={18} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — desktop: static, mobile: slide-in drawer */}
      <aside
        className={cn(
          'h-screen flex-col border-r border-bg-border bg-bg-card/95 backdrop-blur-md shrink-0 z-50',
          mobileOpen
            ? 'flex fixed top-0 left-0 w-64 shadow-2xl animate-slide-in'
            : 'hidden md:flex md:sticky md:top-0 md:w-52',
        )}
      >
        {navContent}
      </aside>
    </>
  )
}
