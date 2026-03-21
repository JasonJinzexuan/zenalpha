import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { scanInstruments, healthCheck, triggerPipeline, getPipelineStatus, triggerDecisions, getLatestDecisions } from '@/api/agent'
import { useWatchlistStore } from '@/stores/watchlist'
import { useStrategyStore } from '@/stores/strategy'
import { cn } from '@/lib/cn'
import { WALK_STATE_LABELS, signalTag, STRUCT } from '@/lib/chan-labels'
import {
  RefreshCw, AlertTriangle, Eye, LayoutDashboard,
  TrendingUp, TrendingDown, Zap, Play, Loader2,
  Brain, ChevronDown, FlaskConical,
} from 'lucide-react'
import type { AnalysisResult, WalkState, Signal, PipelineItem } from '@/types/chan'
import { getSignalType, isBuySignal } from '@/types/chan'
import type { DecisionRecord } from '@/types/api'

type StatusLevel = 'urgent' | 'watch' | 'normal'

interface InstrumentRow {
  item: AnalysisResult
  status: StatusLevel
}

function deriveWalkState(item: AnalysisResult): WalkState {
  if (item.trend?.walk_state) return item.trend.walk_state
  if (item.center_count >= 2 && item.divergence_count > 0) return 'top_divergence'
  if (item.center_count >= 2) return 'up_trend'
  if (item.center_count === 1) return 'consolidation'
  return 'up_trend'
}

function getStatus(signals: Signal[]): StatusLevel {
  const hasSell = signals.some(s => !isBuySignal(s) && getSignalType(s).startsWith('S'))
  if (hasSell) return 'urgent'
  const hasBuy = signals.some(s => isBuySignal(s))
  if (hasBuy) return 'watch'
  return 'normal'
}

const WS_DISPLAY: Record<WalkState, { bg: string; text: string }> = {
  up_trend:          { bg: 'bg-accent-red/8',    text: 'text-accent-red' },
  down_trend:        { bg: 'bg-accent-green/8',  text: 'text-accent-green' },
  consolidation:     { bg: 'bg-accent-yellow/8', text: 'text-accent-yellow' },
  c_extending:       { bg: 'bg-accent-yellow/8', text: 'text-accent-yellow animate-blink' },
  top_divergence:    { bg: 'bg-accent-red/15',   text: 'text-accent-red animate-pulse' },
  bottom_divergence: { bg: 'bg-accent-green/15', text: 'text-accent-green animate-pulse' },
}

function WalkStateCell({ state, signals }: { state: WalkState; signals: Signal[] }) {
  const ws = WALK_STATE_LABELS[state]
  const display = WS_DISPLAY[state] || WS_DISPLAY.consolidation
  const buySignals = signals.filter(s => isBuySignal(s))
  const sellSignals = signals.filter(s => !isBuySignal(s) && getSignalType(s).startsWith('S'))

  return (
    <div className={cn('px-2 py-1.5 rounded text-center min-w-[70px]', display.bg)}>
      <div className={cn('text-[10px] font-semibold', display.text)}>{ws.icon} {ws.label}</div>
      {(buySignals.length > 0 || sellSignals.length > 0) && (
        <div className="flex items-center justify-center gap-1 mt-0.5">
          {buySignals.map((s, i) => (
            <span key={`b${i}`} className="w-1.5 h-1.5 rounded-full bg-accent-green inline-block" title={signalTag(getSignalType(s))} />
          ))}
          {sellSignals.map((s, i) => (
            <span key={`s${i}`} className="w-1.5 h-1.5 rounded-full bg-accent-red inline-block" title={signalTag(getSignalType(s))} />
          ))}
        </div>
      )}
    </div>
  )
}

const OVERALL_STATUS: Record<StatusLevel, { label: string; color: string }> = {
  urgent: { label: '卖出', color: 'text-accent-red bg-accent-red/10 border-accent-red/30' },
  watch:  { label: '买入', color: 'text-accent-green bg-accent-green/10 border-accent-green/30' },
  normal: { label: '-',   color: 'text-text-muted' },
}

export default function OverviewPage() {
  const nav = useNavigate()
  const { instruments } = useWatchlistStore()
  const { activeStrategy } = useStrategyStore()
  const [rows, setRows] = useState<InstrumentRow[]>([])
  const [loading, setLoading] = useState(false)
  const [lastScan, setLastScan] = useState('')
  const [tsStatus, setTsStatus] = useState('unknown')
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [pipelineItems, setPipelineItems] = useState<PipelineItem[]>([])
  const [decisions, setDecisions] = useState<DecisionRecord[]>([])
  const [decisionLoading, setDecisionLoading] = useState(false)

  const runScan = useCallback(async () => {
    setLoading(true)
    try {
      const res = await scanInstruments({ instruments, level: '1d', limit: 500 })
      const mapped: InstrumentRow[] = res.results.map((item: AnalysisResult) => ({
        item,
        status: getStatus(item.signals),
      }))
      mapped.sort((a, b) => {
        const order = { urgent: 0, watch: 1, normal: 2 }
        return order[a.status] - order[b.status]
      })
      setRows(mapped)
      setLastScan(new Date().toLocaleTimeString())
    } catch (err) {
      console.error('Scan failed:', err)
    } finally {
      setLoading(false)
    }
  }, [instruments])

  useEffect(() => { runScan() }, [runScan])

  // Load latest decisions on mount
  useEffect(() => {
    if (instruments.length > 0) {
      getLatestDecisions(instruments).then(r => setDecisions(r.decisions)).catch(() => {})
    }
  }, [instruments])

  async function runDecisionAnalysis() {
    setDecisionLoading(true)
    try {
      const res = await triggerDecisions(instruments, true, activeStrategy)
      setDecisions(prev => [...res.decisions, ...prev])
    } catch { /* ignore */ }
    setDecisionLoading(false)
  }

  useEffect(() => {
    healthCheck().then(r => setTsStatus(r.timestream)).catch(() => {})
  }, [])

  // Quick pipeline trigger
  async function runPipeline() {
    setPipelineLoading(true)
    try {
      await triggerPipeline(instruments, '1d')
      // Poll a few times
      for (let i = 0; i < 10; i++) {
        await new Promise(r => setTimeout(r, 3000))
        const items = await getPipelineStatus(instruments, '1d')
        setPipelineItems(items)
        if (items.every(it => it.status === 'done' || it.status === 'error')) break
      }
    } catch { /* ignore */ }
    setPipelineLoading(false)
  }

  const urgentRows = rows.filter(r => r.status === 'urgent')
  const watchRows = rows.filter(r => r.status === 'watch')
  const totalSignals = rows.reduce((sum, r) => sum + r.item.signals.length, 0)
  const pipelineDone = pipelineItems.filter(i => i.status === 'done').length
  const pipelineSignals = pipelineItems.reduce((sum, i) => sum + (i.signals?.length || 0), 0)

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <LayoutDashboard size={18} className="text-accent-cyan" />
          <h1 className="text-lg font-semibold tracking-[2px] text-text-primary">态势总览</h1>
          <span className="text-[10px] text-text-muted tracking-wider">
            {lastScan ? `上次扫描 ${lastScan}` : '初始化中...'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={runDecisionAnalysis} disabled={decisionLoading} className="btn-ghost text-[10px]">
            {decisionLoading ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
            交易决策
          </button>
          <button onClick={runPipeline} disabled={pipelineLoading} className="btn-ghost text-[10px]">
            {pipelineLoading ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            LLM Pipeline
          </button>
          <button onClick={runScan} disabled={loading} className="btn-primary">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            {loading ? '扫描中...' : '刷新'}
          </button>
        </div>
      </div>

      {/* Live status bar */}
      <div className="flex items-center gap-4 px-4 py-2 bg-bg-card rounded border border-bg-border text-[10px]">
        {tsStatus === 'connected' ? (
          <span className="flex items-center gap-1.5 text-accent-green">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
            实时数据流 (15min延迟)
          </span>
        ) : (
          <span className="text-accent-red">数据源未连接</span>
        )}
        <span className="text-text-muted">|</span>
        <span className="text-text-dim">Timestream: {tsStatus}</span>
        <span className="text-text-muted">|</span>
        <span
          className="flex items-center gap-1 text-accent-purple cursor-pointer hover:text-accent-cyan transition-colors"
          onClick={() => nav('/strategy')}
          title="点击切换策略"
        >
          <FlaskConical size={10} />
          策略: {activeStrategy}
        </span>
        {pipelineItems.length > 0 && (
          <>
            <span className="text-text-muted">|</span>
            <span className="text-accent-purple">Pipeline: {pipelineDone}/{pipelineItems.length} done, {pipelineSignals} signals</span>
          </>
        )}
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="自选列表" value={instruments.length} color="text-accent-cyan" />
        <StatCard label="信号总数" value={totalSignals} color="text-accent-green" />
        <StatCard label="紧急 (卖出)" value={urgentRows.length} color="text-accent-red" />
        <StatCard label="关注 (买入)" value={watchRows.length} color="text-accent-yellow" />
      </div>

      {/* Trading Decisions */}
      {decisions.length > 0 && (
        <div className="card border-accent-cyan/30">
          <div className="card-header text-accent-cyan">
            <span className="flex items-center gap-2"><Brain size={14} /> 交易决策</span>
            <span className="tag tag-cyan">{decisions.length} 条操作建议</span>
          </div>
          <div className="divide-y divide-bg-border">
            {decisions.map((d, i) => (
              <DecisionRow key={`${d.instrument}-${d.timestamp}-${i}`} decision={d} onNavigate={s => nav(`/analysis?symbol=${s}`)} />
            ))}
          </div>
        </div>
      )}

      {/* Urgent signals */}
      {urgentRows.length > 0 && (
        <div className="card border-accent-red/30">
          <div className="card-header text-accent-red">
            <span className="flex items-center gap-2"><AlertTriangle size={12} /> 紧急信号</span>
            <span className="tag tag-red">{urgentRows.length}</span>
          </div>
          <div className="divide-y divide-bg-border">
            {urgentRows.map(({ item }) => (
              <SignalAlertRow key={item.instrument} item={item} onNavigate={s => nav(`/analysis?symbol=${s}`)} />
            ))}
          </div>
        </div>
      )}

      {/* Watch signals */}
      {watchRows.length > 0 && (
        <div className="card border-accent-yellow/20">
          <div className="card-header text-accent-yellow">
            <span className="flex items-center gap-2"><Eye size={12} /> 关注信号</span>
            <span className="tag tag-yellow">{watchRows.length}</span>
          </div>
          <div className="divide-y divide-bg-border">
            {watchRows.map(({ item }) => (
              <SignalAlertRow key={item.instrument} item={item} onNavigate={s => nav(`/analysis?symbol=${s}`)} />
            ))}
          </div>
        </div>
      )}

      {/* Multi-level Status Matrix */}
      <div className="card">
        <div className="card-header">
          多级别状态矩阵
          <span className="tag">{rows.length} 个标的</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-text-muted border-b border-bg-border">
                <th className="text-left px-4 py-2.5 font-medium w-20">标的</th>
                <th className="text-center px-2 py-2.5 font-medium">日线走势</th>
                <th className="text-center px-2 py-2.5 font-medium">{STRUCT.stroke}</th>
                <th className="text-center px-2 py-2.5 font-medium">{STRUCT.segment}</th>
                <th className="text-center px-2 py-2.5 font-medium">{STRUCT.center}</th>
                <th className="text-center px-2 py-2.5 font-medium">{STRUCT.divergence}</th>
                <th className="text-center px-2 py-2.5 font-medium">买卖点</th>
                <th className="text-center px-2 py-2.5 font-medium">状态</th>
                <th className="px-2 py-2.5 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ item, status }) => {
                const walkState = deriveWalkState(item)
                const stCfg = OVERALL_STATUS[status]
                return (
                  <tr
                    key={item.instrument}
                    className="border-b border-bg-border/50 hover:bg-bg-hover cursor-pointer transition-colors"
                    onClick={() => nav(`/analysis?symbol=${item.instrument}`)}
                  >
                    <td className="px-4 py-3 font-bold text-text-primary">{item.instrument}</td>
                    <td className="text-center px-2 py-2">
                      <WalkStateCell state={walkState} signals={item.signals} />
                    </td>
                    <td className="text-center px-2 py-3 text-accent-blue font-medium">{item.stroke_count}</td>
                    <td className="text-center px-2 py-3 text-accent-purple font-medium">{item.segment_count}</td>
                    <td className="text-center px-2 py-3 text-accent-yellow font-medium">{item.center_count}</td>
                    <td className="text-center px-2 py-3">
                      <span className={item.divergence_count > 0 ? 'text-accent-red font-bold' : 'text-text-muted'}>
                        {item.divergence_count}
                      </span>
                    </td>
                    <td className="text-center px-2 py-3">
                      {item.signals.length > 0 ? (
                        <div className="flex items-center justify-center gap-1">
                          {item.signals.map((s, i) => {
                            const type = getSignalType(s)
                            return (
                              <span key={i} className={cn('tag font-semibold', isBuySignal(s) ? 'tag-green' : 'tag-red')}>
                                {signalTag(type)}
                              </span>
                            )
                          })}
                        </div>
                      ) : <span className="text-text-muted">-</span>}
                    </td>
                    <td className="text-center px-2 py-3">
                      {status !== 'normal' ? (
                        <span className={cn('tag font-semibold', stCfg.color)}>{stCfg.label}</span>
                      ) : <span className="text-text-muted">-</span>}
                    </td>
                    <td className="px-2 py-3">
                      <span className="text-[10px] text-accent-cyan">分析 →</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="card px-4 py-3">
      <div className={cn('text-2xl font-bold', color)}>{value}</div>
      <div className="text-[9px] text-text-muted tracking-wider mt-1">{label}</div>
    </div>
  )
}

function DecisionRow({ decision: d, onNavigate }: { decision: DecisionRecord; onNavigate: (s: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const isBuy = d.action === 'BUY'
  const confPct = (d.confidence * 100).toFixed(0)
  const confColor = d.confidence >= 0.7 ? 'text-accent-green' : d.confidence >= 0.4 ? 'text-accent-yellow' : 'text-accent-red'
  const timeStr = new Date(d.timestamp).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="px-4 py-3">
      <div
        className="flex items-center justify-between cursor-pointer hover:bg-bg-hover/30 -mx-4 px-4 py-1 rounded transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className={cn('tag font-bold text-[11px]', isBuy ? 'tag-green' : 'tag-red')}>
            {isBuy ? '买入' : '卖出'}
          </span>
          <span className="text-sm font-bold text-text-primary">{d.instrument}</span>
          {d.price_range_low && d.price_range_high && (
            <span className="text-[10px] text-text-dim">
              价格区间 {d.price_range_low} — {d.price_range_high}
            </span>
          )}
          {d.urgency && (
            <span className={cn('tag text-[9px]', d.urgency === '立即' ? 'tag-red' : 'tag-yellow')}>
              {d.urgency}
            </span>
          )}
          <span className={cn('text-[10px] font-semibold', confColor)}>置信 {confPct}%</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-text-dim">
          <span>{timeStr}</span>
          <ChevronDown size={12} className={cn('transition-transform', expanded && 'rotate-180')} />
          <span className="text-accent-cyan hover:underline" onClick={e => { e.stopPropagation(); onNavigate(d.instrument) }}>分析 →</span>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 space-y-2 text-[11px] pl-2 border-l-2 border-accent-cyan/20 ml-2">
          {d.signal_basis && (
            <div><span className="text-text-muted">信号:</span> <span className="text-text-primary">{d.signal_basis}</span></div>
          )}
          {d.stop_loss && (
            <div><span className="text-text-muted">止损:</span> <span className="text-accent-red">{d.stop_loss}</span></div>
          )}
          {d.position_size && (
            <div><span className="text-text-muted">仓位:</span> <span className="text-text-primary">{d.position_size}</span></div>
          )}
          {d.macro_context && (
            <div className="bg-bg-primary rounded p-2 border border-bg-border/50">
              <div className="text-[9px] text-text-muted mb-0.5">宏观因素</div>
              <div className="text-text-primary">{d.macro_context}</div>
            </div>
          )}
          {d.reasoning && (
            <div className="bg-bg-primary rounded p-2 border border-bg-border/50">
              <div className="text-[9px] text-text-muted mb-0.5">决策推理</div>
              <div className="text-text-primary whitespace-pre-wrap">{d.reasoning}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SignalAlertRow({ item, onNavigate }: { item: AnalysisResult; onNavigate: (s: string) => void }) {
  const walkState = deriveWalkState(item)
  const wsCfg = WALK_STATE_LABELS[walkState]
  return (
    <div
      className="px-4 py-3 flex items-center justify-between hover:bg-bg-hover cursor-pointer transition-colors"
      onClick={() => onNavigate(item.instrument)}
    >
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold text-text-primary">{item.instrument}</span>
        <span className={cn('tag', wsCfg.color)}>{wsCfg.label}</span>
        {item.signals.map((s, i) => {
          const type = getSignalType(s)
          return (
            <span key={i} className={cn('tag font-semibold', isBuySignal(s) ? 'tag-green' : 'tag-red')}>
              {signalTag(type)} {item.level}
            </span>
          )
        })}
      </div>
      <div className="flex items-center gap-4 text-[10px] text-text-dim">
        {item.divergence_count > 0 && (
          <span className="text-accent-red">
            {item.divergences?.[0] && `a=${(+item.divergences[0].a_macd_area).toFixed(1)} c=${(+item.divergences[0].c_macd_area).toFixed(1)}`}
          </span>
        )}
        <span>{item.stroke_count}{STRUCT.stroke} / {item.segment_count}{STRUCT.segment} / {item.center_count}{STRUCT.center}</span>
        <span className="text-accent-cyan hover:underline">详情 →</span>
      </div>
    </div>
  )
}
