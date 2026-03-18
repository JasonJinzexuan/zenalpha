import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ChanChart from '@/components/chart/ChanChart'
import type { AnalysisResult, TimeFrame, WalkState } from '@/types/chan'
import { getSignalType, isBuySignal } from '@/types/chan'
import { cn } from '@/lib/cn'
import { WALK_STATE_LABELS, signalTag, STRUCT } from '@/lib/chan-labels'
import { Search, Map } from 'lucide-react'

const TF_OPTIONS: { label: string; value: TimeFrame }[] = [
  { label: '1分', value: '1m' },
  { label: '5分', value: '5m' },
  { label: '30分', value: '30m' },
  { label: '1时', value: '1h' },
  { label: '日线', value: '1d' },
  { label: '周线', value: '1w' },
  { label: '月线', value: '1M' },
]

function deriveWalkState(a: AnalysisResult): WalkState {
  if (a.trend?.walk_state) return a.trend.walk_state
  if (a.center_count >= 2 && a.divergence_count > 0) return 'top_divergence'
  if (a.center_count >= 2) return 'up_trend'
  if (a.center_count === 1) return 'consolidation'
  return 'up_trend'
}

const WS_CFG: Record<WalkState, { label: string; color: string }> = {
  up_trend:          { label: '上涨趋势（≥2中枢）',   color: 'text-accent-red' },
  down_trend:        { label: '下跌趋势（≥2中枢）',   color: 'text-accent-green' },
  consolidation:     { label: '盘整（1个中枢）',       color: 'text-accent-yellow' },
  c_extending:       { label: 'c段延伸中 ⚡',          color: 'text-accent-yellow' },
  top_divergence:    { label: '顶背驰确认',            color: 'text-accent-red' },
  bottom_divergence: { label: '底背驰确认',            color: 'text-accent-green' },
}

export default function ChartPage() {
  const { symbol = 'AAPL' } = useParams()
  const nav = useNavigate()
  const [tf, setTf] = useState<TimeFrame>('1d')
  const [input, setInput] = useState(symbol)
  const [currentSymbol, setCurrentSymbol] = useState(symbol)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)

  function goToSymbol() {
    const s = input.trim().toUpperCase()
    if (s) {
      setCurrentSymbol(s)
      setAnalysis(null)
      nav(`/chart/${s}`, { replace: true })
    }
  }

  const ws = analysis ? deriveWalkState(analysis) : null
  const wsCfg = ws ? WS_CFG[ws] : null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-[2px]">{currentSymbol}</h1>
          <span className="text-text-muted text-[10px] tracking-wider">缠论分析</span>
        </div>
        <div className="flex items-center gap-2">
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
          <button onClick={() => nav(`/nesting-map/${currentSymbol}`)} className="btn-ghost text-[10px]">
            <Map size={12} /> 区间套
          </button>
        </div>
      </div>

      {/* Timeframe selector */}
      <div className="flex items-center gap-1">
        {TF_OPTIONS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => { setTf(value); setAnalysis(null) }}
            className={cn(
              'px-3 py-1.5 text-[11px] font-medium rounded transition-colors',
              tf === value
                ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30'
                : 'text-text-muted hover:text-text-primary border border-transparent',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main chart with MACD */}
      <div className="card">
        <ChanChart
          instrument={currentSymbol}
          timeframe={tf}
          limit={300}
          height={560}
          showMACD
          onAnalysisComplete={setAnalysis}
        />
      </div>

      {/* Analysis panel */}
      {analysis && (
        <div className="grid grid-cols-3 gap-4">
          {/* Structure info */}
          <div className="card">
            <div className="card-header">当前结构</div>
            <div className="p-4 space-y-3">
              {wsCfg && (
                <div className={cn('text-sm font-bold', wsCfg.color)}>{wsCfg.label}</div>
              )}
              {analysis.trend && (
                <div className="text-[10px] text-text-dim">
                  {analysis.trend.center_count} 个{STRUCT.center} |
                  {analysis.trend.has_segment_c ? ' c段进行中' : ' 结构发展中'} |
                  {analysis.trend.classification === 'up_trend' ? '上涨' : analysis.trend.classification === 'down_trend' ? '下跌' : '盘整'}
                </div>
              )}
              <div className="grid grid-cols-3 gap-2">
                <MetricBox label={STRUCT.kline} value={analysis.kline_count} />
                <MetricBox label={STRUCT.fractal} value={analysis.fractal_count} color="text-accent-orange" />
                <MetricBox label={STRUCT.stroke} value={analysis.stroke_count} color="text-accent-blue" />
                <MetricBox label={STRUCT.segment} value={analysis.segment_count} color="text-accent-purple" />
                <MetricBox label={STRUCT.center} value={analysis.center_count} color="text-accent-yellow" />
                <MetricBox label={STRUCT.divergence} value={analysis.divergence_count} color={analysis.divergence_count > 0 ? 'text-accent-red' : ''} />
              </div>
            </div>
          </div>

          {/* Divergence info */}
          <div className="card">
            <div className="card-header">背驰分析</div>
            <div className="p-4">
              {analysis.divergences?.length > 0 ? (
                <div className="space-y-3">
                  {analysis.divergences.map((d, i) => (
                    <div key={i} className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="tag tag-red font-semibold">{d.type === 'trend' ? '趋势背驰' : '盘整背驰'}</span>
                        <span className="text-[10px] text-text-dim">强度: {(+d.strength * 100).toFixed(0)}%</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div className="bg-accent-blue/5 border border-accent-blue/20 rounded p-2">
                          <div className="text-accent-blue font-semibold">a段</div>
                          <div className="text-text-dim">MACD面积: {(+d.a_macd_area).toFixed(1)}</div>
                          <div className="text-text-dim">DIF极值: {(+d.a_dif_peak).toFixed(2)}</div>
                        </div>
                        <div className="bg-accent-red/5 border border-accent-red/20 rounded p-2">
                          <div className="text-accent-red font-semibold">c段</div>
                          <div className="text-text-dim">MACD面积: {(+d.c_macd_area).toFixed(1)}</div>
                          <div className="text-text-dim">DIF极值: {(+d.c_dif_peak).toFixed(2)}</div>
                        </div>
                      </div>
                      <div className="text-[10px] text-accent-red font-medium">
                        面积比: {((+d.area_ratio) * 100).toFixed(1)}% 缩小
                        {+d.a_dif_peak > 0 && +d.c_dif_peak > 0 && +d.c_dif_peak < +d.a_dif_peak && ' ✓ DIF同步背驰'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-text-muted text-[11px] py-6">当前级别无背驰</div>
              )}
            </div>
          </div>

          {/* Active signals */}
          <div className="card">
            <div className="card-header">
              活跃买卖点
              <span className="tag">{analysis.signals.length}</span>
            </div>
            <div className="p-4">
              {analysis.signals.length > 0 ? (
                <div className="space-y-2">
                  {analysis.signals.map((s, i) => {
                    const type = getSignalType(s)
                    const buy = isBuySignal(s)
                    return (
                      <div key={i} className={cn('p-3 rounded border', buy ? 'border-accent-green/20 bg-accent-green/5' : 'border-accent-red/20 bg-accent-red/5')}>
                        <div className="flex items-center justify-between mb-1">
                          <span className={cn('text-xs font-bold', buy ? 'text-accent-green' : 'text-accent-red')}>{signalTag(type)}</span>
                          <span className="text-[10px] text-accent-cyan">{s.source_lesson}</span>
                        </div>
                        <div className="text-[10px] text-text-dim">
                          价格: {s.price} | 强度: {((+(s.strength || 0)) * 100).toFixed(0)}%
                        </div>
                        {s.reasoning && (
                          <div className="text-[10px] text-text-muted mt-1 leading-relaxed">{s.reasoning}</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center text-text-muted text-[11px] py-6">当前级别无活跃买卖点</div>
              )}

              {/* Center details */}
              {analysis.centers?.length > 0 && (
                <div className="mt-4 pt-3 border-t border-bg-border space-y-2">
                  <div className="text-[10px] text-text-muted tracking-wider font-medium">{STRUCT.center}详情</div>
                  {analysis.centers.map((c, i) => (
                    <div key={i} className="text-[10px] bg-accent-yellow/5 border border-accent-yellow/20 rounded p-2">
                      <div className="flex items-center gap-3">
                        <span className="text-accent-yellow font-semibold">{STRUCT.center} {i + 1}</span>
                        <span className="text-text-dim">扩展: {c.extension_count}次</span>
                      </div>
                      <div className="text-text-dim mt-0.5">
                        ZG={(+c.zg).toFixed(2)} ZD={(+c.zd).toFixed(2)} GG={(+c.gg).toFixed(2)} DD={(+c.dd).toFixed(2)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MetricBox({ label, value, color = '' }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-bg-primary rounded px-2 py-1.5 border border-bg-border/50">
      <div className={cn('text-lg font-bold', color || 'text-text-primary')}>{value}</div>
      <div className="text-[8px] text-text-muted tracking-wider">{label}</div>
    </div>
  )
}
