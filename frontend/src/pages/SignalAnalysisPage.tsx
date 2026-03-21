import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import ChanChart from '@/components/chart/ChanChart'
import { useWatchlistStore } from '@/stores/watchlist'
import { useStrategyStore } from '@/stores/strategy'
import { cn } from '@/lib/cn'
import { signalTag, STRUCT } from '@/lib/chan-labels'
import type { AnalysisResult, TimeFrame, OverlayLayer } from '@/types/chan'
import { getSignalType, isBuySignal } from '@/types/chan'
import { nestingAnalyze, triggerDecisions, getDecisionHistory } from '@/api/agent'
import type { NestingAnalysisResponse, ToolCallLog, PerLevelInfo, DecisionRecord } from '@/types/api'
import {
  Target, Brain, Loader2, ChevronDown, Zap,
  RefreshCw, X, History, FlaskConical,
} from 'lucide-react'

const TF_PANELS: { tf: TimeFrame; label: string; role: string }[] = [
  { tf: '1w', label: '周线', role: '方向层' },
  { tf: '1d', label: '日线', role: '位置层' },
  { tf: '30m', label: '30分钟', role: '精确层' },
  { tf: '5m', label: '5分钟', role: '操作层' },
]

/** Overlay filter options */
const OVERLAY_FILTERS: { key: OverlayLayer; label: string; color: string }[] = [
  { key: 'signals', label: '买卖点 (B1-S3)', color: 'text-accent-green' },
  { key: 'strokes', label: '笔', color: 'text-accent-blue' },
  { key: 'segments', label: '线段', color: 'text-accent-purple' },
  { key: 'centers', label: '中枢', color: 'text-accent-yellow' },
  { key: 'divergence', label: '背驰', color: 'text-accent-red' },
  { key: 'fractals', label: '分型', color: 'text-accent-orange' },
]

interface SignalDetail {
  signal: AnalysisResult['signals'][0]
  timeframe: TimeFrame
  analysis: AnalysisResult
}

/** Explain where the strength value comes from */
function strengthExplanation(signalType: string, strength: number): string {
  const pct = Math.round(strength * 100)
  if (signalType === 'B1' || signalType === 'S1') return '背驰强度'
  if (signalType === 'B2' || signalType === 'S2') {
    if (pct === 70) return '不创新低/高'
    if (pct === 60) return '小转大'
    return '盘整背驰强度'
  }
  if (signalType === 'B3' || signalType === 'S3') return '中枢突破回踩'
  return ''
}

export default function SignalAnalysisPage() {
  const [searchParams] = useSearchParams()
  const { instruments } = useWatchlistStore()
  const { activeStrategy } = useStrategyStore()
  const paramSymbol = searchParams.get('symbol')
  const initialSymbol = paramSymbol && instruments.includes(paramSymbol) ? paramSymbol : instruments[0] || 'AAPL'
  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol)
  const [analyses, setAnalyses] = useState<Record<string, AnalysisResult>>({})
  const [activeLayers, setActiveLayers] = useState<Set<OverlayLayer>>(
    new Set(['signals', 'strokes', 'segments', 'centers'])
  )
  const [selectedSignal, setSelectedSignal] = useState<SignalDetail | null>(null)
  const [llmResult, setLlmResult] = useState<NestingAnalysisResponse | null>(null)
  const [llmLoading, setLlmLoading] = useState(false)
  const [expandedTf, setExpandedTf] = useState<Set<TimeFrame>>(new Set(['1d', '1w', '30m', '5m']))
  const [decisionHistory, setDecisionHistory] = useState<DecisionRecord[]>([])
  const [decisionLoading, setDecisionLoading] = useState(false)
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null)

  // Sync from URL param
  useEffect(() => {
    if (paramSymbol && instruments.includes(paramSymbol) && paramSymbol !== selectedSymbol) {
      setSelectedSymbol(paramSymbol)
    }
  }, [paramSymbol])

  // Reset when instrument changes
  useEffect(() => {
    setAnalyses({})
    setLlmResult(null)
    setSelectedSignal(null)
    // Load decision history
    getDecisionHistory(selectedSymbol, 20)
      .then(r => setDecisionHistory(r.decisions))
      .catch(() => setDecisionHistory([]))
  }, [selectedSymbol])

  const handleAnalysis = useCallback((tf: string, result: AnalysisResult) => {
    setAnalyses(prev => ({ ...prev, [tf]: result }))
  }, [])

  const toggleLayer = (layer: OverlayLayer) => {
    setActiveLayers(prev => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })
  }

  const toggleTf = (tf: TimeFrame) => {
    setExpandedTf(prev => {
      const next = new Set(prev)
      if (next.has(tf)) next.delete(tf)
      else next.add(tf)
      return next
    })
  }

  async function runAIAnalysis() {
    setLlmLoading(true)
    try {
      const result = await nestingAnalyze({ instrument: selectedSymbol, use_llm: true })
      setLlmResult(result)
    } catch (err) {
      console.error('AI analysis failed:', err)
    } finally {
      setLlmLoading(false)
    }
  }

  async function runDecisionAnalysis() {
    setDecisionLoading(true)
    setDecisionMessage(null)
    try {
      const res = await triggerDecisions([selectedSymbol], true, activeStrategy)
      if (res.decisions.length > 0) {
        setDecisionHistory(prev => [...res.decisions, ...prev])
        setDecisionMessage(null)
      } else {
        setDecisionMessage('当前无可执行信号 — 区间套分析未发现符合条件的买卖点')
      }
      // Reload full history
      const history = await getDecisionHistory(selectedSymbol, 20)
      setDecisionHistory(history.decisions)
    } catch (err) {
      console.error('Decision analysis failed:', err)
      setDecisionMessage('决策分析失败，请检查后端服务')
    } finally {
      setDecisionLoading(false)
    }
  }

  const [signalTypeFilter, setSignalTypeFilter] = useState<Set<string>>(new Set(['B1','B2','B3','S1','S2','S3']))

  // Collect all signals across timeframes, sorted by timestamp (chronological timeline)
  const allSignals: SignalDetail[] = TF_PANELS.flatMap(({ tf }) => {
    const a = analyses[tf]
    if (!a) return []
    return a.signals.map(s => ({ signal: s, timeframe: tf, analysis: a }))
  }).sort((a, b) => new Date(a.signal.timestamp).getTime() - new Date(b.signal.timestamp).getTime())

  const filteredSignals = allSignals.filter(sd => signalTypeFilter.has(getSignalType(sd.signal)))

  // Count per type for badge display
  const signalCounts: Record<string, number> = {}
  for (const sd of allSignals) {
    const t = getSignalType(sd.signal)
    signalCounts[t] = (signalCounts[t] || 0) + 1
  }

  // Collect all divergences across timeframes
  const allDivergences = TF_PANELS.flatMap(({ tf }) => {
    const a = analyses[tf]
    if (!a) return []
    return a.divergences.map(d => ({ divergence: d, timeframe: tf }))
  })

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Target size={18} className="text-accent-cyan" />
          <h1 className="text-lg font-semibold tracking-[2px]">标的分析</h1>
          <span className="tag tag-purple flex items-center gap-1">
            <FlaskConical size={10} /> {activeStrategy}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Instrument dropdown */}
          <div className="relative">
            <select
              value={selectedSymbol}
              onChange={e => setSelectedSymbol(e.target.value)}
              className="input w-32 text-xs font-mono appearance-none pr-7 cursor-pointer"
            >
              {instruments.map(sym => (
                <option key={sym} value={sym}>{sym}</option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
          </div>

          {/* Decision trigger */}
          <button onClick={runDecisionAnalysis} disabled={decisionLoading} className="btn-ghost text-[10px] flex items-center gap-1.5">
            {decisionLoading ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            交易决策
          </button>

          {/* AI Analysis button */}
          <button onClick={runAIAnalysis} disabled={llmLoading} className="btn-primary flex items-center gap-1.5">
            {llmLoading ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
            AI 区间套分析
          </button>
        </div>
      </div>

      {/* Filter bars */}
      <div className="flex items-center gap-4 flex-wrap px-1">
        {/* Overlay layers */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-text-muted tracking-wider font-semibold">叠加层:</span>
          {OVERLAY_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => toggleLayer(f.key)}
              className={cn(
                'text-[10px] px-2 py-0.5 rounded border transition-all',
                activeLayers.has(f.key)
                  ? `${f.color} border-current bg-current/10 font-semibold`
                  : 'text-text-muted border-bg-border opacity-50 hover:opacity-75'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        {/* Signal type filter */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-text-muted tracking-wider font-semibold">信号:</span>
          {['B1','B2','B3','S1','S2','S3'].map(type => {
            const active = signalTypeFilter.has(type)
            const isBuy = type.startsWith('B')
            return (
              <button
                key={type}
                onClick={() => setSignalTypeFilter(prev => {
                  const next = new Set(prev)
                  if (next.has(type)) next.delete(type); else next.add(type)
                  return next
                })}
                className={cn(
                  'text-[10px] px-2 py-0.5 rounded border transition-all',
                  active
                    ? isBuy ? 'border-accent-green/50 text-accent-green bg-accent-green/10 font-semibold' : 'border-accent-red/50 text-accent-red bg-accent-red/10 font-semibold'
                    : 'border-bg-border text-text-dim opacity-50',
                )}
              >{type}</button>
            )
          })}
        </div>
      </div>

      {/* Multi-timeframe chart grid */}
      <div className="grid grid-cols-2 gap-3">
        {TF_PANELS.map(({ tf, label, role }) => {
          const isExpanded = expandedTf.has(tf)
          const a = analyses[tf]
          return (
            <div key={tf} className="card">
              {/* TF header */}
              <button
                onClick={() => toggleTf(tf)}
                className="w-full px-3 py-2 flex items-center justify-between hover:bg-bg-hover/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-text-primary">{label}</span>
                  <span className="text-[9px] text-text-muted tracking-wider">{role}</span>
                  {a && (
                    <span className="text-[9px] text-text-dim">
                      {a.stroke_count}{STRUCT.stroke} / {a.segment_count}{STRUCT.segment} / {a.center_count}{STRUCT.center}
                      {a.divergence_count > 0 && <span className="text-accent-red ml-1">{a.divergence_count}{STRUCT.divergence}</span>}
                    </span>
                  )}
                </div>
                <ChevronDown size={12} className={cn('text-text-muted transition-transform', isExpanded && 'rotate-180')} />
              </button>

              {/* Chart */}
              {isExpanded && (
                <div className="border-t border-bg-border">
                  <ChanChart
                    instrument={selectedSymbol}
                    timeframe={tf}
                    limit={tf === '5m' ? 3000 : tf === '30m' ? 2000 : 500}
                    height={320}
                    showMACD={tf === '1d' || tf === '30m'}
                    controlledLayers={Array.from(activeLayers)}
                    signalTypeFilter={signalTypeFilter}
                    onAnalysisComplete={r => handleAnalysis(tf, r)}
                    compact
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Signal timeline — chronological, with strength explanation */}
      {allSignals.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="flex items-center gap-2">
              信号时间线
              <span className="tag tag-cyan">{filteredSignals.length}/{allSignals.length}</span>
            </span>
          </div>
          <div className="divide-y divide-bg-border">
            {filteredSignals.map((sd, i) => {
              const type = getSignalType(sd.signal)
              const buy = isBuySignal(sd.signal)
              const str = sd.signal.strength ? +sd.signal.strength : 0
              const strPct = (str * 100).toFixed(0)
              return (
                <div
                  key={i}
                  className="px-4 py-2.5 flex items-center justify-between hover:bg-bg-hover cursor-pointer transition-colors"
                  onClick={() => setSelectedSignal(sd)}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-[9px] text-text-dim w-12 shrink-0">
                      {new Date(sd.signal.timestamp).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}
                    </span>
                    <span className={cn('tag font-semibold', buy ? 'tag-green' : 'tag-red')}>{signalTag(type)}</span>
                    <span className="tag">{sd.timeframe}</span>
                    <span className="text-[10px] text-text-dim">@ {sd.signal.price}</span>
                    {sd.signal.strength && (
                      <span className="text-[10px] text-text-muted" title={strengthExplanation(type, str)}>
                        强度 {strPct}% <span className="text-[8px] text-text-dim">({strengthExplanation(type, str)})</span>
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-accent-cyan">查看推理 →</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Divergence quantification panel */}
      {allDivergences.length > 0 && (
        <div className="card">
          <div className="card-header">
            背驰量化面板
            <span className="tag tag-red">{allDivergences.length}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-text-muted border-b border-bg-border">
                  <th className="text-left px-4 py-2 font-medium">级别</th>
                  <th className="text-left px-2 py-2 font-medium">类型</th>
                  <th className="text-right px-2 py-2 font-medium">a段MACD面积</th>
                  <th className="text-right px-2 py-2 font-medium">c段MACD面积</th>
                  <th className="text-right px-2 py-2 font-medium">面积比</th>
                  <th className="text-right px-2 py-2 font-medium">强度</th>
                  <th className="px-2 py-2 font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                {allDivergences.map(({ divergence: d, timeframe: tf }, i) => {
                  const aArea = Math.abs(+d.a_macd_area)
                  const cArea = Math.abs(+d.c_macd_area)
                  const ratio = aArea > 0 ? (cArea / aArea * 100).toFixed(1) : '-'
                  const str = +d.strength * 100
                  return (
                    <tr key={i} className="border-b border-bg-border/50 hover:bg-bg-hover/30">
                      <td className="px-4 py-2 font-medium text-text-primary">{tf}</td>
                      <td className="px-2 py-2">
                        <span className={cn('tag', d.type === 'trend' ? 'tag-red' : 'tag-yellow')}>
                          {d.type === 'trend' ? '趋势背驰' : '盘整背驰'}
                        </span>
                      </td>
                      <td className="text-right px-2 py-2 text-text-dim font-mono">{aArea.toFixed(1)}</td>
                      <td className="text-right px-2 py-2 text-text-dim font-mono">{cArea.toFixed(1)}</td>
                      <td className="text-right px-2 py-2">
                        <span className={cn('font-mono font-semibold', +ratio < 80 ? 'text-accent-green' : 'text-accent-yellow')}>
                          {ratio}%
                        </span>
                      </td>
                      <td className="text-right px-2 py-2">
                        <span className={cn('font-semibold', str >= 70 ? 'text-accent-green' : str >= 40 ? 'text-accent-yellow' : 'text-accent-red')}>
                          {str.toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <span className="text-[9px] text-text-dim">
                          {cArea < aArea ? 'c段面积缩小 → 背驰确认' : 'c段面积放大 → 背驰不成立'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* AI Nesting Result */}
      {llmResult && <NestingResultCard result={llmResult} />}

      {/* Decision message when no actionable signal */}
      {decisionMessage && (
        <div className="card border-accent-yellow/30">
          <div className="px-4 py-3 text-[11px] text-accent-yellow flex items-center gap-2">
            <Zap size={14} />
            {decisionMessage}
          </div>
        </div>
      )}

      {/* Decision History */}
      <DecisionHistoryPanel decisions={decisionHistory} />

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal detail={selectedSignal} llmResult={llmResult} onClose={() => setSelectedSignal(null)} />
      )}
    </div>
  )
}

/** Confidence color: >70% green, 40-70% yellow, <40% red */
function confidenceColor(conf: string): string {
  const v = +conf * 100
  if (v >= 70) return 'text-accent-green'
  if (v >= 40) return 'text-accent-yellow'
  return 'text-accent-red'
}

function confidenceBg(conf: string): string {
  const v = +conf * 100
  if (v >= 70) return 'bg-accent-green/10 border-accent-green/30'
  if (v >= 40) return 'bg-accent-yellow/10 border-accent-yellow/30'
  return 'bg-accent-red/10 border-accent-red/30'
}

/** Direction arrow for per-level display */
function directionDisplay(info: PerLevelInfo | undefined): { arrow: string; color: string; label: string } {
  if (!info || !info.direction) return { arrow: '—', color: 'text-text-muted', label: '无数据' }
  if (info.direction === '多') return { arrow: '↑', color: 'text-accent-green', label: '多' }
  return { arrow: '↓', color: 'text-accent-red', label: '空' }
}

const TF_LABELS: Record<string, string> = { '1w': '周线', '1d': '日线', '30m': '30分', '15m': '15分', '1h': '60分', '5m': '5分' }

function NestingResultCard({ result }: { result: NestingAnalysisResponse }) {
  const [showTools, setShowTools] = useState(false)
  const confColor = confidenceColor(result.confidence)
  const confBg = confidenceBg(result.confidence)

  return (
    <div className={cn('card', result.actionable ? 'border-accent-green/30' : 'border-accent-purple/30')}>
      <div className="card-header text-accent-purple">
        <span className="flex items-center gap-2">
          <Brain size={14} />
          AI 区间套分析
          {result.status && (
            <span className={cn('tag text-[9px] font-semibold ml-2', result.actionable ? 'tag-green' : 'tag-yellow')}>
              {result.status}
            </span>
          )}
        </span>
        <span className="text-[9px] text-text-dim">
          {result.confidence_source} · {result.iterations ?? 0} iter · {result.tool_calls?.length ?? 0} tools
        </span>
      </div>
      <div className="p-4 space-y-3">
        {/* Per-level direction alignment bar */}
        {result.per_level && Object.keys(result.per_level).length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-[9px] text-text-muted tracking-wider mr-1">方向:</span>
            {Object.entries(result.per_level).map(([tf, info], i) => {
              const d = directionDisplay(info as PerLevelInfo)
              return (
                <span key={tf} className="flex items-center gap-0.5">
                  {i > 0 && <span className="text-text-muted mx-0.5">|</span>}
                  <span className="text-[9px] text-text-dim">{TF_LABELS[tf] || tf}:</span>
                  <span className={cn('text-[10px] font-bold', d.color)}>{d.arrow} {d.label}</span>
                  {(info as PerLevelInfo)?.signal && (
                    <span className="text-[9px] text-accent-cyan ml-0.5">{(info as PerLevelInfo).signal}</span>
                  )}
                </span>
              )
            })}
          </div>
        )}

        {/* Nesting path */}
        {result.nesting_path?.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] text-text-muted tracking-wider">路径:</span>
            {result.nesting_path.map((p, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <span className="text-text-muted">→</span>}
                <span className="tag">{p}</span>
              </span>
            ))}
          </div>
        )}

        {/* Metrics grid */}
        <div className="grid grid-cols-4 gap-3">
          <MetricBox label="嵌套深度" value={String(result.nesting_depth)} color="text-accent-cyan" />
          <MetricBox
            label="方向对齐"
            value={result.direction_aligned ? '✓ 一致' : '✗ 不一致'}
            color={result.direction_aligned ? 'text-accent-green' : 'text-accent-red'}
          />
          <div className={cn('rounded px-3 py-2 border', confBg)}>
            <div className={cn('text-sm font-bold', confColor)}>{(+result.confidence * 100).toFixed(0)}%</div>
            <div className="text-[9px] text-text-muted">置信度</div>
          </div>
          <MetricBox label="目标级别" value={result.target_level} color="text-text-primary" />
        </div>

        {/* Signals */}
        <div className="flex items-center gap-3 text-[10px]">
          {result.large_signal && <span className="tag tag-cyan">大级别: {result.large_signal}</span>}
          {result.medium_signal && <span className="tag tag-yellow">中级别: {result.medium_signal}</span>}
          {result.precise_signal && <span className="tag tag-green">精确: {result.precise_signal}</span>}
        </div>

        {/* Reasoning — structured Chinese format */}
        {result.reasoning && (
          <div className="bg-bg-primary rounded p-3 border border-bg-border/50">
            <div className="text-[9px] text-text-muted tracking-wider mb-1">AI 推理</div>
            <div className="text-[11px] text-text-primary leading-relaxed whitespace-pre-wrap">{result.reasoning}</div>
          </div>
        )}

        {/* Risk */}
        {result.risk_assessment && (
          <div className="bg-accent-red/5 rounded p-3 border border-accent-red/20">
            <div className="text-[9px] text-accent-red tracking-wider mb-1">风险评估</div>
            <div className="text-[11px] text-text-primary leading-relaxed">{result.risk_assessment}</div>
          </div>
        )}

        {/* Tool calls */}
        {result.tool_calls?.length > 0 && (
          <div>
            <button onClick={() => setShowTools(!showTools)} className="flex items-center gap-1.5 text-[9px] text-text-dim hover:text-accent-cyan transition-colors">
              <Zap size={10} />
              {showTools ? '收起' : '展开'} Tool Calls ({result.tool_calls.length})
            </button>
            {showTools && (
              <div className="mt-2 space-y-1">
                {result.tool_calls.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-[9px] py-1 px-2 bg-bg-primary/50 rounded border border-bg-border/30">
                    <span className="text-text-muted w-4">#{c.iteration}</span>
                    <span className="text-accent-cyan font-mono">{c.tool}</span>
                    <span className="text-text-dim truncate flex-1">{JSON.stringify(c.args)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function SignalDetailModal({
  detail,
  llmResult,
  onClose,
}: {
  detail: SignalDetail
  llmResult: NestingAnalysisResponse | null
  onClose: () => void
}) {
  const { signal: s, timeframe, analysis } = detail
  const type = getSignalType(s)
  const buy = isBuySignal(s)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-bg-card border border-bg-border rounded-lg w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-bg-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={cn('text-lg font-bold', buy ? 'text-accent-green' : 'text-accent-red')}>
              {signalTag(type)}
            </span>
            <span className="tag">{timeframe}</span>
            <span className="text-[11px] text-text-dim">@ {s.price}</span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-bg-hover rounded transition-colors text-text-muted hover:text-text-primary">
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Signal basics */}
          <div className="grid grid-cols-3 gap-3 text-[11px]">
            <div>
              <span className="text-text-muted">级别</span>
              <div className="text-text-primary font-medium">{timeframe}</div>
            </div>
            <div>
              <span className="text-text-muted">价格</span>
              <div className="text-text-primary font-medium">{s.price}</div>
            </div>
            <div>
              <span className="text-text-muted">强度</span>
              <div className="text-text-primary font-medium">
                {s.strength ? `${(+s.strength * 100).toFixed(0)}%` : '-'}
                {s.strength && (
                  <span className="text-[9px] text-text-dim ml-1">({strengthExplanation(type, +s.strength)})</span>
                )}
              </div>
            </div>
          </div>

          {/* Reasoning from signal */}
          {s.reasoning && (
            <div className="bg-bg-primary rounded p-3 border border-bg-border/50">
              <div className="text-[10px] text-text-muted tracking-wider mb-1">信号推理</div>
              <div className="text-[11px] text-text-primary leading-relaxed">{s.reasoning}</div>
            </div>
          )}

          {/* Source lesson */}
          {s.source_lesson && (
            <div className="bg-accent-cyan/5 rounded p-3 border border-accent-cyan/20">
              <div className="text-[10px] text-accent-cyan tracking-wider mb-1">来源规则</div>
              <div className="text-[11px] text-text-primary">{s.source_lesson}</div>
            </div>
          )}

          {/* Structure context at signal time */}
          <div>
            <div className="text-[10px] text-text-muted tracking-wider mb-2">信号触发时结构</div>
            <div className="grid grid-cols-5 gap-2">
              <SnapshotBox label={STRUCT.stroke} value={analysis.stroke_count} color="text-accent-blue" />
              <SnapshotBox label={STRUCT.segment} value={analysis.segment_count} color="text-accent-purple" />
              <SnapshotBox label={STRUCT.center} value={analysis.center_count} color="text-accent-yellow" />
              <SnapshotBox label={STRUCT.divergence} value={analysis.divergence_count} color={analysis.divergence_count > 0 ? 'text-accent-red' : ''} />
              <SnapshotBox label="K线" value={analysis.kline_count} />
            </div>
          </div>

          {/* Divergence detail if present */}
          {analysis.divergences?.length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] text-text-muted tracking-wider">背驰详情</div>
              {analysis.divergences.map((d, i) => (
                <div key={i} className="text-[10px] bg-accent-red/5 border border-accent-red/20 rounded p-2 space-y-0.5">
                  <div className="text-accent-red font-semibold">{d.type === 'trend' ? '趋势背驰' : '盘整背驰'}</div>
                  <div className="text-text-dim">a段MACD: {(+d.a_macd_area).toFixed(1)} → c段: {(+d.c_macd_area).toFixed(1)} (缩小{((+d.area_ratio) * 100).toFixed(1)}%)</div>
                  <div className="text-text-dim">强度: {(+d.strength * 100).toFixed(0)}%</div>
                </div>
              ))}
            </div>
          )}

          {/* AI reasoning from nesting analysis */}
          {llmResult?.reasoning && (
            <div className="bg-accent-purple/5 rounded p-3 border border-accent-purple/20">
              <div className="text-[10px] text-accent-purple tracking-wider mb-1">AI 区间套推理</div>
              <div className="text-[11px] text-text-primary leading-relaxed whitespace-pre-wrap">{llmResult.reasoning}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function DecisionHistoryPanel({ decisions }: { decisions: DecisionRecord[] }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  if (decisions.length === 0) return null

  return (
    <div className="card">
      <div className="card-header">
        <span className="flex items-center gap-2"><History size={14} /> 历史交易决策</span>
        <span className="tag">{decisions.length}</span>
      </div>
      <div className="divide-y divide-bg-border">
        {decisions.map((d, i) => {
          const isBuy = d.action === 'BUY'
          const expanded = expandedIdx === i
          const confPct = (d.confidence * 100).toFixed(0)
          const confColor = d.confidence >= 0.7 ? 'text-accent-green' : d.confidence >= 0.4 ? 'text-accent-yellow' : 'text-accent-red'
          const timeStr = new Date(d.timestamp).toLocaleString('zh-CN', {
            year: 'numeric', month: 'numeric', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })

          return (
            <div key={`${d.timestamp}-${i}`} className="px-4 py-2.5">
              <div
                className="flex items-center justify-between cursor-pointer hover:bg-bg-hover/30 -mx-2 px-2 py-1 rounded transition-colors"
                onClick={() => setExpandedIdx(expanded ? null : i)}
              >
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-text-dim w-28 shrink-0">{timeStr}</span>
                  <span className={cn('tag font-bold', isBuy ? 'tag-green' : 'tag-red')}>
                    {isBuy ? '买入' : '卖出'}
                  </span>
                  {d.price_range_low && d.price_range_high && (
                    <span className="text-[10px] text-text-dim">
                      {d.price_range_low} — {d.price_range_high}
                    </span>
                  )}
                  {d.urgency && (
                    <span className={cn('tag text-[9px]', d.urgency === '立即' ? 'tag-red' : 'tag-yellow')}>
                      {d.urgency}
                    </span>
                  )}
                  <span className={cn('text-[10px] font-semibold', confColor)}>置信 {confPct}%</span>
                </div>
                <ChevronDown size={12} className={cn('text-text-muted transition-transform', expanded && 'rotate-180')} />
              </div>
              {expanded && (
                <div className="mt-2 space-y-2 text-[11px] pl-4 border-l-2 border-accent-cyan/20 ml-2">
                  {d.signal_basis && (
                    <div><span className="text-text-muted">信号依据:</span> <span className="text-text-primary">{d.signal_basis}</span></div>
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
        })}
      </div>
    </div>
  )
}

function MetricBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
      <div className={cn('text-sm font-bold', color)}>{value}</div>
      <div className="text-[9px] text-text-muted">{label}</div>
    </div>
  )
}

function SnapshotBox({ label, value, color = '' }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-bg-primary rounded px-2 py-1.5 border border-bg-border/50">
      <div className={cn('text-sm font-bold', color || 'text-text-primary')}>{value}</div>
      <div className="text-[8px] text-text-muted">{label}</div>
    </div>
  )
}
