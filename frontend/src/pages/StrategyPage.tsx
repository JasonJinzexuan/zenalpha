import { useState, useEffect, useMemo } from 'react'
import {
  FlaskConical, Play, Save, Loader2, CheckCircle2, XCircle,
  TrendingUp, TrendingDown, BarChart3, Settings2, Zap, Shield,
  Power, History, Trash2, ChevronDown, ChevronUp,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { useStrategyStore } from '@/stores/strategy'
import {
  getStrategyTemplates, runStrategyBacktest, runSensitivity, saveStrategy,
} from '@/api/agent'
import type {
  StrategyTemplate, StrategyParams, RiskParams, StrategyBacktestResponse,
  SensitivityResponse, QualificationGate,
} from '@/types/api'

// ── Parameter metadata for UI controls ──────────────────────────────────────

interface ParamMeta {
  key: string
  label: string
  type: 'number' | 'decimal' | 'boolean' | 'signals'
  min?: number
  max?: number
  step?: number
  pct?: boolean
}

const STRATEGY_DEFS: ParamMeta[] = [
  { key: 'min_nesting_depth', label: '最小嵌套深度', type: 'number', min: 1, max: 4 },
  { key: 'min_confidence', label: '最小置信度', type: 'decimal', min: 0, max: 1, step: 0.05, pct: true },
  { key: 'require_alignment', label: '要求方向一致', type: 'boolean' },
  { key: 'divergence_ratio_max', label: '背驰比率上限', type: 'decimal', min: 0.3, max: 1.5, step: 0.05 },
  { key: 'min_signal_strength', label: '最小信号强度', type: 'decimal', min: 0, max: 1, step: 0.05, pct: true },
  { key: 'allowed_signals', label: '允许信号', type: 'signals' },
]

const RISK_DEFS: ParamMeta[] = [
  { key: 'stop_loss_atr_mult', label: '止损ATR倍数', type: 'decimal', min: 0.5, max: 5, step: 0.5 },
  { key: 'take_profit_atr_mult', label: '止盈ATR倍数', type: 'decimal', min: 1, max: 10, step: 0.5 },
  { key: 'trailing_stop_pct', label: '追踪止损%', type: 'decimal', min: 0, max: 0.2, step: 0.01, pct: true },
  { key: 'max_position_pct', label: '最大仓位%', type: 'decimal', min: 0.01, max: 0.15, step: 0.01, pct: true },
  { key: 'max_concurrent_positions', label: '最大持仓数', type: 'number', min: 1, max: 20 },
  { key: 'max_daily_loss_pct', label: '单日最大亏损%', type: 'decimal', min: 0.01, max: 0.1, step: 0.01, pct: true },
  { key: 'max_weekly_loss_pct', label: '单周最大亏损%', type: 'decimal', min: 0.02, max: 0.2, step: 0.01, pct: true },
  { key: 'max_drawdown_pct', label: '最大回撤%', type: 'decimal', min: 0.05, max: 0.3, step: 0.01, pct: true },
]

const ALL_SIGNALS = ['B1', 'B2', 'B3', 'S1', 'S2', 'S3']

const DEFAULT_INSTRUMENTS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
  'JPM', 'V', 'UNH', 'XOM', 'JNJ', 'WMT', 'PG', 'MA', 'HD',
  'COST', 'ABBV', 'CRM',
]

const SENSITIVITY_PARAMS = [
  { key: 'min_nesting_depth', label: '最小嵌套深度', values: ['1', '2', '3', '4'] },
  { key: 'min_confidence', label: '最小置信度', values: ['0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8'] },
  { key: 'stop_loss_atr_mult', label: '止损ATR倍数', values: ['1.0', '1.5', '2.0', '2.5', '3.0', '4.0'] },
  { key: 'max_position_pct', label: '最大仓位%', values: ['0.02', '0.03', '0.05', '0.08', '0.10'] },
]

// ── Main component ──────────────────────────────────────────────────────────

export default function StrategyPage() {
  const [templates, setTemplates] = useState<StrategyTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [strategyP, setStrategyP] = useState<StrategyParams | null>(null)
  const [riskP, setRiskP] = useState<RiskParams | null>(null)
  const [loading, setLoading] = useState(false)
  const [backtestResult, setBacktestResult] = useState<StrategyBacktestResponse | null>(null)
  const [sensResult, setSensResult] = useState<SensitivityResponse | null>(null)
  const [sensLoading, setSensLoading] = useState(false)
  const [sensParam, setSensParam] = useState(SENSITIVITY_PARAMS[0].key)
  const [saveMsg, setSaveMsg] = useState('')
  const [tab, setTab] = useState<'backtest' | 'sensitivity' | 'history'>('backtest')
  const [instruments, setInstruments] = useState<string[]>([...DEFAULT_INSTRUMENTS])
  const [instrumentInput, setInstrumentInput] = useState('')
  const { activeStrategy, activate, switchHistory, clearHistory } = useStrategyStore()

  useEffect(() => {
    getStrategyTemplates()
      .then(r => {
        setTemplates(r.templates)
        if (r.templates.length > 0) {
          setSelectedTemplate(r.templates[0].name)
          setStrategyP(r.templates[0].strategy)
          setRiskP(r.templates[0].risk)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const t = templates.find(t => t.name === selectedTemplate)
    if (t) {
      setStrategyP({ ...t.strategy })
      setRiskP({ ...t.risk })
    }
  }, [selectedTemplate, templates])

  const updateStrategy = (key: string, value: unknown) => {
    if (!strategyP) return
    setStrategyP({ ...strategyP, [key]: value })
  }

  const updateRisk = (key: string, value: unknown) => {
    if (!riskP) return
    setRiskP({ ...riskP, [key]: value })
  }

  const toggleSignal = (sig: string) => {
    if (!strategyP) return
    const current = strategyP.allowed_signals
    const next = current.includes(sig)
      ? current.filter(s => s !== sig)
      : [...current, sig]
    updateStrategy('allowed_signals', next)
  }

  const handleBacktest = async () => {
    if (!strategyP || !riskP) return
    setLoading(true)
    setBacktestResult(null)
    try {
      const result = await runStrategyBacktest({ strategy: strategyP, risk: riskP, instruments })
      setBacktestResult(result)
    } catch (e: any) {
      console.error('Backtest failed:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSensitivity = async () => {
    if (!strategyP || !riskP) return
    setSensLoading(true)
    setSensResult(null)
    const sp = SENSITIVITY_PARAMS.find(p => p.key === sensParam)
    if (!sp) return
    try {
      const result = await runSensitivity({
        param_name: sp.key,
        values: sp.values,
        base_strategy: strategyP,
        base_risk: riskP,
        instruments,
      })
      setSensResult(result)
    } catch (e: any) {
      console.error('Sensitivity failed:', e)
    } finally {
      setSensLoading(false)
    }
  }

  const handleSave = async () => {
    if (!strategyP || !riskP) return
    const name = `custom_${Date.now()}`
    try {
      await saveStrategy(name, strategyP, riskP)
      setSaveMsg(`Saved as "${name}"`)
      setTimeout(() => setSaveMsg(''), 3000)
    } catch {
      setSaveMsg('Save failed')
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <FlaskConical size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">策略实验室</h1>
      </div>

      {/* Active strategy indicator */}
      <div className="flex items-center gap-3 px-4 py-2 bg-bg-card rounded border border-bg-border text-[10px]">
        <span className="text-text-dim">当前激活策略:</span>
        <span className="text-accent-cyan font-medium">{activeStrategy}</span>
        {selectedTemplate !== activeStrategy && (
          <button
            className="btn btn-primary text-[10px] py-0.5 px-2"
            onClick={() => activate(selectedTemplate)}
          >
            <Power size={10} /> 激活 "{selectedTemplate}"
          </button>
        )}
        {selectedTemplate === activeStrategy && (
          <span className="tag tag-green">已激活</span>
        )}
      </div>

      {/* Instrument selector */}
      <div className="card">
        <div className="card-header">
          <span className="text-[11px] text-text-muted">回测标的 ({instruments.length}/{DEFAULT_INSTRUMENTS.length})</span>
          <div className="flex items-center gap-2">
            <button className="text-[10px] text-accent-cyan hover:underline" onClick={() => setInstruments([...DEFAULT_INSTRUMENTS])}>全选</button>
            <button className="text-[10px] text-accent-cyan hover:underline" onClick={() => setInstruments([])}>清空</button>
          </div>
        </div>
        <div className="p-3 space-y-2">
          <div className="flex flex-wrap gap-1">
            {DEFAULT_INSTRUMENTS.map(inst => (
              <button
                key={inst}
                className={cn(
                  'text-[10px] px-2 py-0.5 rounded border transition-colors',
                  instruments.includes(inst)
                    ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10'
                    : 'border-bg-border text-text-dim',
                )}
                onClick={() => setInstruments(prev =>
                  prev.includes(inst) ? prev.filter(i => i !== inst) : [...prev, inst]
                )}
              >{inst}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              className="input-field text-[10px] flex-1"
              placeholder="添加自定义标的 (如 BABA)"
              value={instrumentInput}
              onChange={e => setInstrumentInput(e.target.value.toUpperCase())}
              onKeyDown={e => {
                if (e.key === 'Enter' && instrumentInput.trim()) {
                  const sym = instrumentInput.trim()
                  if (!instruments.includes(sym)) setInstruments(prev => [...prev, sym])
                  setInstrumentInput('')
                }
              }}
            />
            <button
              className="btn btn-ghost text-[10px]"
              onClick={() => {
                if (instrumentInput.trim() && !instruments.includes(instrumentInput.trim())) {
                  setInstruments(prev => [...prev, instrumentInput.trim()])
                }
                setInstrumentInput('')
              }}
            >添加</button>
          </div>
        </div>
      </div>

      {/* Template selector + tabs */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          className="input-field w-48"
          value={selectedTemplate}
          onChange={e => setSelectedTemplate(e.target.value)}
        >
          {templates.map(t => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
        </select>

        <div className="flex gap-1">
          <button className={cn('btn', tab === 'backtest' ? 'btn-primary' : 'btn-ghost')} onClick={() => setTab('backtest')}>
            <Play size={12} /> 回测
          </button>
          <button className={cn('btn', tab === 'sensitivity' ? 'btn-primary' : 'btn-ghost')} onClick={() => setTab('sensitivity')}>
            <BarChart3 size={12} /> 敏感度
          </button>
          <button className={cn('btn', tab === 'history' ? 'btn-primary' : 'btn-ghost')} onClick={() => setTab('history')}>
            <History size={12} /> 切换历史
          </button>
        </div>

        <button className="btn btn-ghost ml-auto" onClick={handleSave}>
          <Save size={12} /> 保存
        </button>
        {saveMsg && <span className="text-[10px] text-accent-green">{saveMsg}</span>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Parameter controls — split into two cards */}
        <div className="lg:col-span-1 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Strategy params */}
          <div className="card">
            <div className="card-header">
              <span className="flex items-center gap-2"><Settings2 size={12} /> 策略参数</span>
              <span className="text-[9px] text-text-dim">LLM参考</span>
            </div>
            <div className="p-3 space-y-3">
              {strategyP && STRATEGY_DEFS.map(meta => (
                <ParamControl
                  key={meta.key}
                  meta={meta}
                  value={(strategyP as any)[meta.key]}
                  onChange={(v) => updateStrategy(meta.key, v)}
                  onToggleSignal={toggleSignal}
                  allowedSignals={strategyP.allowed_signals}
                />
              ))}
            </div>
          </div>

          {/* Risk params */}
          <div className="card">
            <div className="card-header">
              <span className="flex items-center gap-2"><Shield size={12} /> 风控参数</span>
              <span className="text-[9px] text-accent-red">硬规则</span>
            </div>
            <div className="p-3 space-y-3">
              {riskP && RISK_DEFS.map(meta => (
                <ParamControl
                  key={meta.key}
                  meta={meta}
                  value={(riskP as any)[meta.key]}
                  onChange={(v) => updateRisk(meta.key, v)}
                  onToggleSignal={() => {}}
                  allowedSignals={[]}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2 space-y-4">
          {tab === 'backtest' && (
            <div className="card">
              <div className="card-header">
                <span className="flex items-center gap-2"><Zap size={12} /> 回测执行</span>
                <button className="btn btn-primary" onClick={handleBacktest} disabled={loading}>
                  {loading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                  {loading ? '运行中...' : '运行回测'}
                </button>
              </div>
              {backtestResult && (
                <div className="p-4 space-y-4">
                  <QualificationBanner qualified={backtestResult.qualified} gates={backtestResult.qualification} />
                  <MetricsGrid metrics={backtestResult.metrics} />
                  <QualificationGates gates={backtestResult.qualification} />
                  {backtestResult.signal_stats.length > 0 && <SignalStatsTable stats={backtestResult.signal_stats} />}
                  {backtestResult.trade_log?.length > 0 && <TradeLogTable trades={backtestResult.trade_log} />}
                  {backtestResult.equity_curve.length > 0 && <EquityCurve data={backtestResult.equity_curve} />}
                </div>
              )}
              {!backtestResult && !loading && (
                <div className="p-8 text-center text-text-muted text-[11px]">调整参数后点击"运行回测"查看结果</div>
              )}
            </div>
          )}

          {tab === 'sensitivity' && (
            <div className="card">
              <div className="card-header">
                <span className="flex items-center gap-2"><BarChart3 size={12} /> 参数敏感度分析</span>
                <div className="flex items-center gap-2">
                  <select className="input-field text-[10px] w-36" value={sensParam} onChange={e => setSensParam(e.target.value)}>
                    {SENSITIVITY_PARAMS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
                  </select>
                  <button className="btn btn-primary" onClick={handleSensitivity} disabled={sensLoading}>
                    {sensLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    运行
                  </button>
                </div>
              </div>
              {sensResult && <div className="p-4"><SensitivityTable data={sensResult} /></div>}
              {!sensResult && !sensLoading && (
                <div className="p-8 text-center text-text-muted text-[11px]">选择参数后点击"运行"查看不同参数值的回测对比</div>
              )}
            </div>
          )}

          {tab === 'history' && (
            <div className="card">
              <div className="card-header">
                <span className="flex items-center gap-2"><History size={12} /> 策略切换历史</span>
                {switchHistory.length > 0 && (
                  <button className="btn btn-ghost text-[10px]" onClick={clearHistory}><Trash2 size={10} /> 清空</button>
                )}
              </div>
              {switchHistory.length === 0 ? (
                <div className="p-8 text-center text-text-muted text-[11px]">暂无策略切换记录</div>
              ) : (
                <div className="divide-y divide-bg-border">
                  {switchHistory.map((r, i) => (
                    <div key={i} className="px-4 py-2 flex items-center gap-3 text-[11px]">
                      <span className="text-text-dim w-36 shrink-0">{new Date(r.timestamp).toLocaleString('zh-CN')}</span>
                      <span className="tag tag-yellow">{r.from}</span>
                      <span className="text-text-dim">{'→'}</span>
                      <span className="tag tag-cyan">{r.to}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────────────────

function ParamControl({ meta, value, onChange, onToggleSignal, allowedSignals }: {
  meta: ParamMeta; value: unknown; onChange: (v: unknown) => void
  onToggleSignal: (s: string) => void; allowedSignals: string[]
}) {
  if (meta.type === 'boolean') {
    return (
      <label className="flex items-center justify-between text-[11px]">
        <span className="text-text-muted">{meta.label}</span>
        <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} className="accent-accent-cyan" />
      </label>
    )
  }
  if (meta.type === 'signals') {
    return (
      <div className="space-y-1">
        <div className="text-[11px] text-text-muted">{meta.label}</div>
        <div className="flex flex-wrap gap-1">
          {ALL_SIGNALS.map(sig => (
            <button key={sig} className={cn(
              'text-[10px] px-2 py-0.5 rounded border transition-colors',
              allowedSignals.includes(sig)
                ? sig.startsWith('B') ? 'border-accent-red/50 text-accent-red bg-accent-red/10' : 'border-accent-green/50 text-accent-green bg-accent-green/10'
                : 'border-bg-border text-text-dim',
            )} onClick={() => onToggleSignal(sig)}>{sig}</button>
          ))}
        </div>
      </div>
    )
  }
  const numVal = meta.type === 'number' ? Number(value) : parseFloat(String(value))
  const displayVal = meta.pct ? `${(numVal * 100).toFixed(0)}%` : numVal
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-text-muted">{meta.label}</span>
        <span className="text-text-primary font-medium">{displayVal}</span>
      </div>
      <input type="range" min={meta.min ?? 0} max={meta.max ?? 10} step={meta.step ?? 1} value={numVal}
        onChange={e => { const v = meta.type === 'number' ? parseInt(e.target.value) : e.target.value; onChange(v) }}
        className="w-full h-1 accent-accent-cyan bg-bg-border rounded-lg appearance-none cursor-pointer" />
    </div>
  )
}

function QualificationBanner({ qualified, gates }: { qualified: boolean; gates: Record<string, QualificationGate> }) {
  const passCount = Object.values(gates).filter(g => g.pass).length
  const total = Object.keys(gates).length
  return (
    <div className={cn('flex items-center gap-3 px-4 py-3 rounded-lg border', qualified ? 'border-accent-green/30 bg-accent-green/5' : 'border-accent-red/30 bg-accent-red/5')}>
      {qualified ? <CheckCircle2 size={18} className="text-accent-green" /> : <XCircle size={18} className="text-accent-red" />}
      <div>
        <div className={cn('text-xs font-medium', qualified ? 'text-accent-green' : 'text-accent-red')}>{qualified ? '策略合格' : '策略未达标'}</div>
        <div className="text-[10px] text-text-dim">通过 {passCount}/{total} 项资格检查</div>
      </div>
    </div>
  )
}

function MetricsGrid({ metrics }: { metrics: StrategyBacktestResponse['metrics'] }) {
  const items = [
    { label: '总收益', value: metrics.total_return, pct: true },
    { label: '年化收益', value: metrics.annualized_return, pct: true },
    { label: 'Sharpe', value: metrics.sharpe_ratio },
    { label: 'Sortino', value: metrics.sortino_ratio },
    { label: 'Calmar', value: metrics.calmar_ratio },
    { label: '最大回撤', value: metrics.max_drawdown, pct: true, bad: true },
    { label: '胜率', value: metrics.win_rate, pct: true },
    { label: '盈亏比', value: metrics.profit_factor },
    { label: '总交易', value: String(metrics.total_trades) },
    { label: '平均盈亏', value: metrics.avg_trade_pnl },
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {items.map(item => {
        const num = parseFloat(item.value)
        const isNeg = num < 0
        const display = item.pct ? `${(num * 100).toFixed(2)}%` : num.toFixed(4)
        return (
          <div key={item.label} className="bg-bg-primary rounded p-2 text-center">
            <div className="text-[10px] text-text-dim">{item.label}</div>
            <div className={cn('text-xs font-medium mt-0.5', item.bad ? (isNeg ? 'text-accent-green' : 'text-accent-red') : (isNeg ? 'text-accent-red' : 'text-accent-green'))}>{display}</div>
          </div>
        )
      })}
    </div>
  )
}

function QualificationGates({ gates }: { gates: Record<string, QualificationGate> }) {
  const labels: Record<string, string> = { win_rate: '胜率', profit_factor: '盈亏比', max_drawdown: '最大回撤', sharpe_ratio: 'Sharpe' }
  return (
    <div className="space-y-1">
      <div className="text-[11px] text-text-muted mb-1">资格检查</div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {Object.entries(gates).map(([key, gate]) => {
          const val = parseFloat(gate.value); const thresh = parseFloat(gate.threshold)
          const isPct = key === 'win_rate' || key === 'max_drawdown'
          const fmt = (n: number) => isPct ? `${(n * 100).toFixed(1)}%` : n.toFixed(3)
          return (
            <div key={key} className={cn('rounded p-2 border text-center', gate.pass ? 'border-accent-green/20 bg-accent-green/5' : 'border-accent-red/20 bg-accent-red/5')}>
              <div className="text-[10px] text-text-dim">{labels[key] || key}</div>
              <div className={cn('text-xs font-medium', gate.pass ? 'text-accent-green' : 'text-accent-red')}>{fmt(val)}</div>
              <div className="text-[9px] text-text-dim">{key === 'max_drawdown' ? '<=' : '>='} {fmt(thresh)}</div>
              {gate.pass ? <CheckCircle2 size={10} className="text-accent-green mx-auto mt-0.5" /> : <XCircle size={10} className="text-accent-red mx-auto mt-0.5" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SignalStatsTable({ stats }: { stats: StrategyBacktestResponse['signal_stats'] }) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] text-text-muted">决策维度统计</div>
      <table className="w-full text-[10px]">
        <thead><tr className="text-text-dim border-b border-bg-border"><th className="text-left py-1 px-2">决策类型</th><th className="text-right py-1 px-2">交易数</th><th className="text-right py-1 px-2">胜率</th><th className="text-right py-1 px-2">总盈亏</th></tr></thead>
        <tbody>
          {stats.map(s => {
            const wr = parseFloat(s.win_rate) * 100; const pnl = parseFloat(s.total_pnl)
            return (
              <tr key={s.signal_type} className="border-b border-bg-border/50">
                <td className="py-1 px-2 text-text-primary">{s.signal_type}</td>
                <td className="text-right py-1 px-2 text-text-primary">{s.trades}</td>
                <td className="text-right py-1 px-2 text-text-primary">{wr.toFixed(1)}%</td>
                <td className={cn('text-right py-1 px-2', pnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>{pnl.toFixed(2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TradeLogTable({ trades }: { trades: StrategyBacktestResponse['trade_log'] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="space-y-1">
      <button
        className="flex items-center justify-between w-full text-[11px] text-text-muted hover:text-text-primary"
        onClick={() => setOpen(!open)}
      >
        <span>交易记录 ({trades.length})</span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div className="max-h-[300px] overflow-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-text-dim border-b border-bg-border sticky top-0 bg-bg-card">
                <th className="text-left py-1 px-2">时间</th>
                <th className="text-left py-1 px-2">标的</th>
                <th className="text-left py-1 px-2">方向</th>
                <th className="text-right py-1 px-2">价格</th>
                <th className="text-left py-1 px-2">信号</th>
                <th className="text-center py-1 px-2">嵌套</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => {
                const isBuy = t.action === 'BUY'
                const ts = t.timestamp.includes('T')
                  ? t.timestamp.slice(0, 16).replace('T', ' ')
                  : t.timestamp.slice(0, 16)
                return (
                  <tr key={i} className="border-b border-bg-border/50">
                    <td className="py-1 px-2 text-text-dim">{ts}</td>
                    <td className="py-1 px-2 text-text-primary">{t.instrument}</td>
                    <td className="py-1 px-2">
                      <span className={cn('tag', isBuy ? 'tag-red' : 'tag-green')}>
                        {isBuy ? '买入' : '卖出'}
                      </span>
                    </td>
                    <td className="text-right py-1 px-2 text-text-primary">{parseFloat(t.price).toFixed(2)}</td>
                    <td className="py-1 px-2 text-text-dim">{t.signal}</td>
                    <td className="text-center py-1 px-2 text-text-dim">
                      {t.nesting_depth > 0 ? `${t.nesting_depth}层${t.aligned ? '✓' : '✗'}` : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function EquityCurve({ data }: { data: { timestamp: string; equity: string }[] }) {
  const points = useMemo(() => data.map(d => parseFloat(d.equity)), [data])
  const minVal = Math.min(...points); const maxVal = Math.max(...points)
  const range = maxVal - minVal || 1; const h = 120; const w = 600
  const pathD = useMemo(() => points.map((v, i) => {
    const x = (i / (points.length - 1)) * w; const y = h - ((v - minVal) / range) * h
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' '), [points, minVal, range])
  const initial = points[0]; const final = points[points.length - 1]
  const returnPct = ((final - initial) / initial * 100).toFixed(2)
  const isPositive = final >= initial
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="text-[11px] text-text-muted">净值曲线</div>
        <div className={cn('text-[11px] font-medium', isPositive ? 'text-accent-green' : 'text-accent-red')}>
          {isPositive ? <TrendingUp size={10} className="inline mr-1" /> : <TrendingDown size={10} className="inline mr-1" />}{returnPct}%
        </div>
      </div>
      <div className="bg-bg-primary rounded p-2 overflow-hidden">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-28"><path d={pathD} fill="none" stroke={isPositive ? '#22c55e' : '#ef4444'} strokeWidth="1.5" /></svg>
      </div>
      <div className="flex justify-between text-[9px] text-text-dim px-1"><span>{data[0]?.timestamp.slice(0, 10)}</span><span>{data[data.length - 1]?.timestamp.slice(0, 10)}</span></div>
    </div>
  )
}

function SensitivityTable({ data }: { data: SensitivityResponse }) {
  const best = useMemo(() => {
    let idx = 0, bs = -Infinity
    data.results.forEach((r, i) => { const s = parseFloat(r.sharpe_ratio); if (s > bs) { bs = s; idx = i } })
    return idx
  }, [data])
  return (
    <div className="space-y-2">
      <div className="text-[11px] text-text-muted">参数: <span className="text-text-primary font-medium">{data.param_name}</span></div>
      <table className="w-full text-[10px]">
        <thead><tr className="text-text-dim border-b border-bg-border"><th className="text-left py-1 px-2">参数值</th><th className="text-right py-1 px-2">胜率</th><th className="text-right py-1 px-2">Sharpe</th><th className="text-right py-1 px-2">回撤</th><th className="text-right py-1 px-2">盈亏比</th><th className="text-right py-1 px-2">总收益</th><th className="text-right py-1 px-2">交易数</th></tr></thead>
        <tbody>
          {data.results.map((r, i) => {
            const ret = parseFloat(r.total_return) * 100; const wr = parseFloat(r.win_rate) * 100; const dd = parseFloat(r.max_drawdown) * 100
            return (
              <tr key={r.param_value} className={cn('border-b border-bg-border/50', i === best && 'bg-accent-cyan/5')}>
                <td className="py-1 px-2 text-text-primary font-medium">{r.param_value}{i === best && <span className="tag tag-cyan ml-1">BEST</span>}</td>
                <td className="text-right py-1 px-2">{wr.toFixed(1)}%</td>
                <td className="text-right py-1 px-2">{parseFloat(r.sharpe_ratio).toFixed(3)}</td>
                <td className="text-right py-1 px-2 text-accent-red">{dd.toFixed(1)}%</td>
                <td className="text-right py-1 px-2">{parseFloat(r.profit_factor).toFixed(3)}</td>
                <td className={cn('text-right py-1 px-2', ret >= 0 ? 'text-accent-green' : 'text-accent-red')}>{ret.toFixed(2)}%</td>
                <td className="text-right py-1 px-2">{r.total_trades}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
