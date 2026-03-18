import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { WALK_STATE_LABELS, signalTag } from '@/lib/chan-labels'
import type { Position, WalkState } from '@/types/chan'
import { Briefcase, TrendingUp, TrendingDown, Map, LineChart, AlertTriangle } from 'lucide-react'

const DEMO_POSITIONS: (Position & { multiLevel: Record<string, WalkState> })[] = [
  {
    id: '1', instrument: 'MSFT', entrySignal: 'B2', entryPrice: 420.30, entryDate: '2026-03-01',
    allocation: 60, currentPnl: 8.2, stopLoss: 415.80, costZeroProgress: 80, tTrades: 3, status: 'open',
    multiLevel: { '1w': 'up_trend', '1d': 'c_extending', '30m': 'consolidation' },
  },
  {
    id: '2', instrument: 'NVDA', entrySignal: 'B3', entryPrice: 850.20, entryDate: '2026-03-15',
    allocation: 100, currentPnl: 3.1, stopLoss: 847.50, costZeroProgress: 20, tTrades: 0, status: 'open',
    multiLevel: { '1w': 'up_trend', '1d': 'top_divergence', '30m': 'consolidation', '5m': 'up_trend' },
  },
  {
    id: '3', instrument: 'AMZN', entrySignal: 'B1', entryPrice: 180.00, entryDate: '2026-02-10',
    allocation: 0, currentPnl: 8.3, stopLoss: 0, costZeroProgress: 100, tTrades: 5, status: 'closed',
    exitPrice: 195.00, exitDate: '2026-03-10', exitReason: '二卖触发', signalCorrect: true,
    multiLevel: {},
  },
  {
    id: '4', instrument: 'GOOGL', entrySignal: 'B2', entryPrice: 160.00, entryDate: '2026-02-20',
    allocation: 0, currentPnl: -2.1, stopLoss: 0, costZeroProgress: 0, tTrades: 0, status: 'closed',
    exitPrice: 156.64, exitDate: '2026-03-05', exitReason: '止损DD触及', signalCorrect: false,
    multiLevel: {},
  },
]

function getOperationHint(pos: typeof DEMO_POSITIONS[0]): { text: string; rule: string; severity: 'warning' | 'danger' | 'info' } | null {
  const ml = pos.multiLevel
  const daily = ml['1d']
  const m30 = ml['30m']

  if (daily === 'top_divergence') {
    return {
      text: '日线进入背驰区间，上方空间可能有限',
      rule: '定理10.2: 日线确认一卖时，减仓50%',
      severity: 'warning',
    }
  }
  if (m30 === 'top_divergence' || m30 === 'down_trend') {
    return {
      text: '大买小卖 → 小级别减仓，等待重新介入',
      rule: '定理8.5: 减仓至40%，30分钟一买重新进场',
      severity: 'info',
    }
  }
  return null
}

export default function PositionsPage() {
  const nav = useNavigate()
  const [positions] = useState(DEMO_POSITIONS)

  const openPositions = positions.filter(p => p.status === 'open')
  const closedPositions = positions.filter(p => p.status === 'closed')

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Briefcase size={18} className="text-accent-cyan" />
          <h1 className="text-lg font-semibold tracking-[2px]">持仓管理</h1>
        </div>
        <span className="tag tag-cyan">{openPositions.length} 持仓中</span>
      </div>

      {/* Open positions */}
      <div className="space-y-3">
        {openPositions.map(pos => {
          const hint = getOperationHint(pos)
          return (
            <div key={pos.id} className={cn('card', hint?.severity === 'danger' ? 'border-accent-red/40' : hint?.severity === 'warning' ? 'border-accent-yellow/30' : '')}>
              <div className="px-4 py-3 flex items-center justify-between border-b border-bg-border">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-text-primary">{pos.instrument}</span>
                  <span className="tag tag-green">{signalTag(pos.entrySignal)} @ ${pos.entryPrice}</span>
                  <span className="text-[10px] text-text-muted">仓位: {pos.allocation}%</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={cn('text-sm font-bold', pos.currentPnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>
                    {pos.currentPnl >= 0 ? '+' : ''}{pos.currentPnl}%
                  </span>
                  {pos.currentPnl >= 0
                    ? <TrendingUp size={14} className="text-accent-green" />
                    : <TrendingDown size={14} className="text-accent-red" />}
                </div>
              </div>

              <div className="p-4 space-y-3">
                <div className="grid grid-cols-4 gap-3 text-[10px]">
                  <div>
                    <span className="text-text-muted">入场</span>
                    <div className="text-text-primary font-medium">{signalTag(pos.entrySignal)} {pos.entryDate}</div>
                  </div>
                  <div>
                    <span className="text-text-muted">止损 (DD)</span>
                    <div className="text-accent-red font-medium">${pos.stopLoss}</div>
                  </div>
                  <div>
                    <span className="text-text-muted">成本归零进度</span>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-accent-cyan rounded-full transition-all" style={{ width: `${pos.costZeroProgress}%` }} />
                      </div>
                      <span className="text-accent-cyan font-medium">{pos.costZeroProgress}%</span>
                    </div>
                  </div>
                  <div>
                    <span className="text-text-muted">T操作次数</span>
                    <div className="text-text-primary font-medium">{pos.tTrades}</div>
                  </div>
                </div>

                {/* Multi-level status */}
                <div>
                  <div className="text-[9px] text-text-muted tracking-wider mb-1.5">多级别走势状态</div>
                  <div className="flex items-center gap-2">
                    {Object.entries(pos.multiLevel).map(([tf, ws]) => {
                      const cfg = WALK_STATE_LABELS[ws]
                      const isDangerous = ws === 'top_divergence' || ws === 'down_trend'
                      return (
                        <div key={tf} className={cn('text-[10px] px-2 py-1 rounded border', isDangerous ? 'border-accent-red/30 bg-accent-red/5' : 'border-bg-border bg-bg-primary')}>
                          <span className="text-text-muted">{tf}: </span>
                          <span className={cn('font-semibold', cfg.color)}>{cfg.label}</span>
                          {isDangerous && <AlertTriangle size={10} className="text-accent-red ml-1 inline" />}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {hint && (
                  <div className={cn(
                    'p-3 rounded border text-[10px]',
                    hint.severity === 'danger' ? 'border-accent-red/30 bg-accent-red/5' :
                    hint.severity === 'warning' ? 'border-accent-yellow/30 bg-accent-yellow/5' :
                    'border-accent-cyan/20 bg-accent-cyan/5'
                  )}>
                    <div className={cn(
                      'font-semibold mb-1',
                      hint.severity === 'danger' ? 'text-accent-red' :
                      hint.severity === 'warning' ? 'text-accent-yellow' :
                      'text-accent-cyan'
                    )}>
                      {hint.severity === 'danger' ? '紧急' : hint.severity === 'warning' ? '操作提示' : '建议'}
                    </div>
                    <div className="text-text-primary">{hint.text}</div>
                    <div className="text-text-muted mt-1">{hint.rule}</div>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button onClick={() => nav(`/nesting-map/${pos.instrument}`)} className="btn-ghost text-[10px]">
                    <Map size={11} /> 区间套
                  </button>
                  <button onClick={() => nav(`/chart/${pos.instrument}`)} className="btn-ghost text-[10px]">
                    <LineChart size={11} /> 图表
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {closedPositions.length > 0 && (
        <div className="card">
          <div className="card-header">
            已平仓
            <span className="tag">{closedPositions.length}</span>
          </div>
          <div className="divide-y divide-bg-border">
            {closedPositions.map(pos => (
              <div key={pos.id} className="px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-text-primary">{pos.instrument}</span>
                  <span className="text-[10px] text-text-muted">
                    {signalTag(pos.entrySignal)}@${pos.entryPrice} → ${pos.exitPrice}
                  </span>
                  <span className="text-[10px] text-text-dim">{pos.exitReason}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={cn('text-xs font-bold', pos.currentPnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>
                    {pos.currentPnl >= 0 ? '+' : ''}{pos.currentPnl}%
                  </span>
                  <span className={cn('tag font-semibold', pos.signalCorrect ? 'tag-green' : 'tag-red')}>
                    {pos.signalCorrect ? '正确 ✓' : '错误 ✗'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
