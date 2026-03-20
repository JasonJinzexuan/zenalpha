import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ChanChart from '@/components/chart/ChanChart'
import { useWatchlistStore } from '@/stores/watchlist'
import { cn } from '@/lib/cn'
import { WALK_STATE_LABELS, signalTag, STRUCT } from '@/lib/chan-labels'
import type { AnalysisResult, TimeFrame, WalkState } from '@/types/chan'
import { getSignalType, isBuySignal } from '@/types/chan'
import { nestingAnalyze } from '@/api/agent'
import type { NestingAnalysisResponse, ToolCallLog } from '@/types/api'
import { Search, Layers, ChevronDown, Brain, Loader2, Zap } from 'lucide-react'

interface NestingLevel {
  timeframe: TimeFrame
  role: string
  label: string
  roleColor: string
}

const NESTING_LEVELS: NestingLevel[] = [
  { timeframe: '1w', role: '方向', label: '周线 — 方向层', roleColor: 'bg-accent-cyan/10 text-accent-cyan' },
  { timeframe: '1d', role: '位置', label: '日线 — 位置层', roleColor: 'bg-accent-yellow/10 text-accent-yellow' },
  { timeframe: '30m', role: '精确', label: '30分 — 精确层', roleColor: 'bg-accent-purple/10 text-accent-purple' },
  { timeframe: '5m', role: '操作', label: '5分 — 操作层', roleColor: 'bg-accent-green/10 text-accent-green' },
]

function deriveWalkState(a: AnalysisResult): WalkState {
  if (a.trend?.walk_state) return a.trend.walk_state
  if (a.center_count >= 2 && a.divergence_count > 0) return 'top_divergence'
  if (a.center_count >= 2) return 'up_trend'
  if (a.center_count === 1) return 'consolidation'
  return 'up_trend'
}

export default function NestingMapPage() {
  const { symbol } = useParams()
  const nav = useNavigate()
  const { instruments } = useWatchlistStore()
  const [selectedSymbol, setSelectedSymbol] = useState(symbol || instruments[0] || 'AAPL')
  const [input, setInput] = useState(selectedSymbol)
  const [analyses, setAnalyses] = useState<Record<string, AnalysisResult>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ '1d': true })
  const [llmResult, setLlmResult] = useState<NestingAnalysisResponse | null>(null)
  const [llmLoading, setLlmLoading] = useState(false)

  useEffect(() => {
    if (symbol && symbol !== selectedSymbol) {
      setSelectedSymbol(symbol)
      setInput(symbol)
      setAnalyses({})
      setLlmResult(null)
    }
  }, [symbol])

  function goToSymbol() {
    const s = input.trim().toUpperCase()
    if (s) {
      setSelectedSymbol(s)
      setAnalyses({})
      setLlmResult(null)
      nav(`/nesting-map/${s}`, { replace: true })
    }
  }

  async function runLLMNesting() {
    setLlmLoading(true)
    try {
      const result = await nestingAnalyze({ instrument: selectedSymbol, use_llm: true })
      setLlmResult(result)
    } catch (err) {
      console.error('LLM nesting failed:', err)
    } finally {
      setLlmLoading(false)
    }
  }

  function handleAnalysis(tf: string, result: AnalysisResult) {
    setAnalyses(prev => ({ ...prev, [tf]: result }))
  }

  const toggle = (tf: string) => setExpanded(prev => ({ ...prev, [tf]: !prev[tf] }))
  const allAnalyses = NESTING_LEVELS.map(l => analyses[l.timeframe])
  const hasAllData = allAnalyses.every(Boolean)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Layers size={18} className="text-accent-cyan" />
          <h1 className="text-lg font-semibold tracking-[2px]">{selectedSymbol}</h1>
          <span className="text-text-muted text-[10px] tracking-wider">区间套分析</span>
        </div>
        <div className="flex items-center">
          <div className="flex items-center gap-1 bg-bg-card border border-bg-border rounded overflow-hidden">
            <input
              className="bg-transparent px-3 py-1.5 text-xs text-text-primary outline-none w-24 font-mono"
              value={input}
              onChange={e => setInput(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && goToSymbol()}
              placeholder="代码"
            />
            <button onClick={goToSymbol} className="px-2 py-1.5 text-text-muted hover:text-accent-cyan transition-colors">
              <Search size={13} />
            </button>
          </div>
          <button onClick={runLLMNesting} disabled={llmLoading} className="btn-primary flex items-center gap-1.5 ml-2">
            {llmLoading ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
            AI分析
          </button>
        </div>
      </div>

      {/* Nesting layers */}
      <div className="space-y-2">
        {NESTING_LEVELS.map((level, idx) => {
          const a = analyses[level.timeframe] || null
          const isExpanded = expanded[level.timeframe]
          const ws = a ? deriveWalkState(a) : null
          const wsCfg = ws ? WALK_STATE_LABELS[ws] : null

          return (
            <div key={level.timeframe}>
              {idx > 0 && (
                <div className="flex items-center gap-2 py-1 pl-8">
                  <ChevronDown size={12} className="text-text-muted" />
                  <span className="text-[9px] text-text-muted tracking-wider">
                    {NESTING_LEVELS[idx - 1].timeframe.toUpperCase()} c段 → {level.timeframe.toUpperCase()} 区间
                  </span>
                </div>
              )}

              <div className={cn(
                'card',
                a?.divergence_count ? 'border-accent-red/30' :
                a?.signals?.length ? 'border-accent-green/30' :
                'border-bg-border'
              )}>
                <div
                  className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-bg-hover transition-colors"
                  onClick={() => toggle(level.timeframe)}
                >
                  <div className="flex items-center gap-3">
                    <span className={cn('text-[10px] px-2 py-0.5 rounded font-semibold tracking-wider', level.roleColor)}>
                      {level.role}
                    </span>
                    <span className="text-xs text-text-primary font-medium">{level.label}</span>
                    {wsCfg && (
                      <span className={cn('text-[11px] font-semibold', wsCfg.color)}>
                        {wsCfg.icon} {wsCfg.label}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {a && (
                      <span className="text-[10px] text-text-dim">
                        {a.stroke_count}{STRUCT.stroke} / {a.segment_count}{STRUCT.segment} / {a.center_count}{STRUCT.center}
                        {a.divergence_count > 0 && <span className="text-accent-red ml-1">{a.divergence_count}{STRUCT.divergence}</span>}
                      </span>
                    )}
                    {a?.signals?.map((s, i) => {
                      const type = getSignalType(s)
                      return <span key={i} className={cn('tag font-semibold', isBuySignal(s) ? 'tag-green' : 'tag-red')}>{signalTag(type)}</span>
                    })}
                    <ChevronDown size={14} className={cn('text-text-muted transition-transform', isExpanded && 'rotate-180')} />
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-bg-border">
                    {a && (
                      <div className="px-4 py-2 bg-bg-primary/50 text-[10px] space-y-1.5">
                        <div className="flex items-center gap-3 flex-wrap">
                          {wsCfg && <span className={cn('font-semibold', wsCfg.color)}>{wsCfg.label}</span>}
                          {a.trend && (
                            <span className="text-text-dim">
                              {a.trend.center_count} 个{STRUCT.center} | {a.trend.has_segment_c ? 'c段进行中' : '无c段'}
                            </span>
                          )}
                        </div>

                        {a.divergences?.length > 0 && a.divergences.map((d, i) => (
                          <div key={i} className="flex items-center gap-4 text-accent-red">
                            <span className="font-semibold">{d.type === 'trend' ? '趋势背驰' : '盘整背驰'}</span>
                            <span>a段MACD: {(+d.a_macd_area).toFixed(1)}</span>
                            <span>c段MACD: {(+d.c_macd_area).toFixed(1)}</span>
                            <span>差值: {((+d.area_ratio) * 100).toFixed(1)}%</span>
                            <span>DIF极值: a={(+d.a_dif_peak).toFixed(2)} c={(+d.c_dif_peak).toFixed(2)}</span>
                            <span>强度: {(+d.strength * 100).toFixed(0)}%</span>
                          </div>
                        ))}

                        <div className="text-text-muted">
                          {level.role === '方向' && (
                            <>方向判断: {ws === 'up_trend' || ws === 'c_extending' ? '看多 ✓ 买点有效' : ws === 'down_trend' || ws === 'top_divergence' ? '看空 ✗ 谨慎做多' : '中性 — 等待'}</>
                          )}
                          {level.role === '位置' && (
                            <>位置判断: {a.divergence_count > 0 ? '进入背驰区间' : a.trend?.has_segment_c ? 'c段延伸中' : '结构发展中'}</>
                          )}
                          {level.role === '精确' && (
                            <>精确判断: {a.signals?.length > 0 ? `活跃: ${a.signals.map(s => signalTag(getSignalType(s))).join(', ')}` : '等待买卖点确认'}</>
                          )}
                          {level.role === '操作' && (
                            <>操作判断: {a.signals?.length > 0 ? `入场点: ${a.signals.map(s => `${signalTag(getSignalType(s))} @ ${s.price}`).join(', ')}` : '暂无入场点'}</>
                          )}
                        </div>
                      </div>
                    )}

                    <ChanChart
                      instrument={selectedSymbol}
                      timeframe={level.timeframe}
                      limit={200}
                      height={320}
                      showMACD={level.role === '位置' || level.role === '精确'}
                      onAnalysisComplete={r => handleAnalysis(level.timeframe, r)}
                      compact
                    />
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* LLM Nesting Analysis */}
      {llmResult && (
        <div className="card border-accent-purple/30">
          <div className="card-header text-accent-purple">
            <span className="flex items-center gap-2"><Brain size={14} /> AI 区间套分析</span>
            <span className="text-[9px] text-text-dim">{llmResult.confidence_source} · {llmResult.iterations} iterations · {llmResult.tool_calls.length} tool calls</span>
          </div>
          <div className="p-4 space-y-3">
            {/* Path */}
            {llmResult.nesting_path.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] text-text-muted tracking-wider">路径:</span>
                {llmResult.nesting_path.map((p, i) => (
                  <span key={i} className="flex items-center gap-1">
                    {i > 0 && <span className="text-text-muted">→</span>}
                    <span className="tag">{p}</span>
                  </span>
                ))}
              </div>
            )}

            {/* Metrics */}
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
                <div className="text-sm font-bold text-accent-cyan">{llmResult.nesting_depth}</div>
                <div className="text-[9px] text-text-muted">嵌套深度</div>
              </div>
              <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
                <div className={cn('text-sm font-bold', llmResult.direction_aligned ? 'text-accent-green' : 'text-accent-red')}>
                  {llmResult.direction_aligned ? '✓ 一致' : '✗ 不一致'}
                </div>
                <div className="text-[9px] text-text-muted">方向对齐</div>
              </div>
              <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
                <div className="text-sm font-bold text-accent-yellow">{(+llmResult.confidence * 100).toFixed(0)}%</div>
                <div className="text-[9px] text-text-muted">置信度</div>
              </div>
              <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
                <div className="text-sm font-bold text-text-primary">{llmResult.target_level}</div>
                <div className="text-[9px] text-text-muted">目标级别</div>
              </div>
            </div>

            {/* Signals */}
            <div className="flex items-center gap-3 text-[10px]">
              {llmResult.large_signal && <span className="tag tag-cyan">大级别: {llmResult.large_signal}</span>}
              {llmResult.medium_signal && <span className="tag tag-yellow">中级别: {llmResult.medium_signal}</span>}
              {llmResult.precise_signal && <span className="tag tag-green">精确: {llmResult.precise_signal}</span>}
            </div>

            {/* Reasoning */}
            {llmResult.reasoning && (
              <div className="bg-bg-primary rounded p-3 border border-bg-border/50">
                <div className="text-[9px] text-text-muted tracking-wider mb-1">AI 推理</div>
                <div className="text-[11px] text-text-primary leading-relaxed whitespace-pre-wrap">{llmResult.reasoning}</div>
              </div>
            )}

            {/* Risk */}
            {llmResult.risk_assessment && (
              <div className="bg-accent-red/5 rounded p-3 border border-accent-red/20">
                <div className="text-[9px] text-accent-red tracking-wider mb-1">风险评估</div>
                <div className="text-[11px] text-text-primary leading-relaxed">{llmResult.risk_assessment}</div>
              </div>
            )}

            {/* Tool calls */}
            {llmResult.tool_calls.length > 0 && (
              <ToolCallTimeline calls={llmResult.tool_calls} />
            )}
          </div>
        </div>
      )}

      {/* Nesting conclusion */}
      <div className="card border-accent-cyan/20">
        <div className="card-header">区间套综合结论</div>
        <div className="p-4">
          {hasAllData ? (
            <NestingConclusion analyses={analyses} symbol={selectedSymbol} />
          ) : (
            <div className="text-center text-text-muted text-[11px] py-4">
              展开全部4个层级以生成区间套结论。点击各层标题展开。
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function NestingConclusion({ analyses, symbol }: { analyses: Record<string, AnalysisResult>; symbol: string }) {
  const pathParts = NESTING_LEVELS.map(l => {
    const a = analyses[l.timeframe]
    if (!a) return { tf: l.timeframe, state: '?', color: '' }
    const ws = deriveWalkState(a)
    const cfg = WALK_STATE_LABELS[ws]
    return { tf: l.timeframe, state: ws, label: cfg.label, color: cfg.color }
  })

  const allSignals = NESTING_LEVELS.flatMap(l => {
    const a = analyses[l.timeframe]
    return a ? a.signals.map(s => ({ ...s, _tf: l.timeframe })) : []
  })

  const totalDiv = NESTING_LEVELS.reduce((sum, l) => sum + (analyses[l.timeframe]?.divergence_count || 0), 0)
  const depth = NESTING_LEVELS.filter(l => {
    const a = analyses[l.timeframe]
    return a && (a.signals.length > 0 || a.divergence_count > 0)
  }).length

  const weeklyWS = analyses['1w'] ? deriveWalkState(analyses['1w']) : null
  const operationSignals = analyses['5m']?.signals || []
  const directionAligned = weeklyWS &&
    (weeklyWS === 'up_trend' || weeklyWS === 'c_extending') &&
    operationSignals.some(s => isBuySignal(s))

  return (
    <div className="space-y-4">
      {/* Path */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-text-muted tracking-wider font-medium">路径:</span>
        {pathParts.map((p, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-text-muted">→</span>}
            <span className={cn('tag font-semibold', p.color)}>{p.tf.toUpperCase()}:{p.label}</span>
          </span>
        ))}
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
          <div className="text-sm font-bold text-accent-cyan">{depth}</div>
          <div className="text-[9px] text-text-muted tracking-wider">嵌套深度</div>
        </div>
        <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
          <div className="text-sm font-bold text-accent-yellow">{totalDiv}</div>
          <div className="text-[9px] text-text-muted tracking-wider">总{STRUCT.divergence}数</div>
        </div>
        <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
          <div className="text-sm font-bold text-accent-green">{allSignals.length}</div>
          <div className="text-[9px] text-text-muted tracking-wider">活跃买卖点</div>
        </div>
        <div className="bg-bg-primary rounded px-3 py-2 border border-bg-border/50">
          <div className={cn('text-sm font-bold', directionAligned ? 'text-accent-green' : 'text-accent-red')}>
            {directionAligned ? '✓ 一致' : '✗ 不一致'}
          </div>
          <div className="text-[9px] text-text-muted tracking-wider">方向对齐</div>
        </div>
      </div>

      {/* Signals across all levels */}
      {allSignals.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-text-muted tracking-wider font-medium">各级别买卖点:</div>
          {allSignals.map((s: any, i: number) => {
            const type = getSignalType(s)
            const buy = isBuySignal(s)
            return (
              <div key={i} className={cn('p-2.5 rounded border text-[10px]', buy ? 'border-accent-green/20 bg-accent-green/5' : 'border-accent-red/20 bg-accent-red/5')}>
                <div className="flex items-center gap-3">
                  <span className={cn('font-bold', buy ? 'text-accent-green' : 'text-accent-red')}>{signalTag(type)}</span>
                  <span className="tag">{s._tf}</span>
                  <span className="text-text-dim">@ {s.price}</span>
                  {s.strength && <span className="text-text-muted">强度: {(+s.strength * 100).toFixed(0)}%</span>}
                  {s.source_lesson && <span className="text-accent-cyan">{s.source_lesson}</span>}
                </div>
                {s.reasoning && <div className="text-text-muted mt-1 leading-relaxed">{s.reasoning}</div>}
              </div>
            )
          })}
        </div>
      )}

      {/* Operation suggestion */}
      <div className="bg-bg-primary rounded p-3 border border-accent-cyan/20">
        <div className="text-[10px] text-accent-cyan font-semibold tracking-wider mb-1">操作建议</div>
        <div className="text-[11px] text-text-primary leading-relaxed">
          {directionAligned && operationSignals.length > 0 ? (
            <>
              方向对齐（周线↑）。操作级别有 {operationSignals.map(s => signalTag(getSignalType(s))).join(', ')}。
              可按区间套规则介入。{depth}层确认。
            </>
          ) : totalDiv > 0 && !directionAligned ? (
            <>
              检测到背驰但方向不一致，风险较高。
              等待操作级别确认或减小仓位。
            </>
          ) : (
            <>
              暂无明确操作点。继续监控。
              展开所有层级，等待操作级别买卖点确认。
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ToolCallTimeline({ calls }: { calls: ToolCallLog[] }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div>
      <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1.5 text-[9px] text-text-dim hover:text-accent-cyan transition-colors">
        <Zap size={10} />
        {expanded ? '收起' : '展开'} Tool Calls ({calls.length})
      </button>
      {expanded && (
        <div className="mt-2 space-y-1">
          {calls.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-[9px] py-1 px-2 bg-bg-primary/50 rounded border border-bg-border/30">
              <span className="text-text-muted w-4">#{c.iteration}</span>
              <span className="text-accent-cyan font-mono">{c.tool}</span>
              <span className="text-text-dim truncate flex-1">{JSON.stringify(c.args)}</span>
              {c.result_summary && (
                <span className="text-accent-green shrink-0">
                  {(c.result_summary as any).signal_count != null ? `${(c.result_summary as any).signal_count} signals` : ''}
                  {(c.result_summary as any).trend ? ` · ${(c.result_summary as any).trend}` : ''}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
