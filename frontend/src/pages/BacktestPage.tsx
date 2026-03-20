import { useState } from 'react'
import { runNestingBacktest } from '@/api/agent'
import { cn } from '@/lib/cn'
import type { BacktestResponse, TradeLogEntry } from '@/types/api'
import { FlaskConical, Play, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'

export default function BacktestPage() {
  const [instruments, setInstruments] = useState('AAPL,MSFT,NVDA')
  const [initialCash, setInitialCash] = useState('1000000')
  const [minDepth, setMinDepth] = useState(2)
  const [requireAlignment, setRequireAlignment] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResponse | null>(null)
  const [error, setError] = useState('')
  const [showLog, setShowLog] = useState(false)

  async function handleRun() {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const symbols = instruments.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean)
      const res = await runNestingBacktest({
        instruments: symbols,
        initial_cash: initialCash,
        min_nesting_depth: minDepth,
        require_alignment: requireAlignment,
      })
      setResult(res)
    } catch (e: any) {
      setError(e.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <FlaskConical size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">NESTING BACKTEST</h1>
      </div>

      {/* Config */}
      <div className="card">
        <div className="card-header">CONFIGURATION</div>
        <div className="p-4 space-y-3">
          <div>
            <label className="text-[10px] text-text-muted tracking-wider block mb-1">INSTRUMENTS (comma-separated)</label>
            <input className="input w-full" value={instruments} onChange={(e) => setInstruments(e.target.value)} />
          </div>
          <div className="flex items-center gap-4">
            <div>
              <label className="text-[10px] text-text-muted tracking-wider block mb-1">INITIAL CAPITAL</label>
              <input className="input w-48" value={initialCash} onChange={(e) => setInitialCash(e.target.value)} />
            </div>
            <div>
              <label className="text-[10px] text-text-muted tracking-wider block mb-1">MIN NESTING DEPTH</label>
              <select className="input w-24" value={minDepth} onChange={(e) => setMinDepth(+e.target.value)}>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </select>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <input
                type="checkbox"
                id="align"
                checked={requireAlignment}
                onChange={(e) => setRequireAlignment(e.target.checked)}
                className="accent-accent-cyan"
              />
              <label htmlFor="align" className="text-[10px] text-text-muted tracking-wider">REQUIRE ALIGNMENT</label>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleRun} disabled={loading} className="btn-primary">
              <Play size={12} />
              {loading ? 'RUNNING...' : 'RUN BACKTEST'}
            </button>
            {loading && <span className="text-[10px] text-text-muted animate-pulse">Fetching multi-TF data & running nesting backtest...</span>}
          </div>
          <div className="text-[9px] text-text-dim">
            Multi-timeframe nesting: 1w/1d/30m/5m pipelines per instrument.
            Only executes signals with depth &ge; {minDepth} {requireAlignment ? '+ direction aligned' : ''}.
            Data fetched from InfluxDB automatically.
          </div>
        </div>
      </div>

      {error && (
        <div className="text-accent-red text-[11px] bg-accent-red/5 border border-accent-red/20 rounded px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="card">
            <div className="card-header">RESULTS</div>
            <div className="p-4 space-y-4">
              {result.total_trades === 0 && (
                <div className="flex items-center gap-2 text-accent-yellow text-[11px] bg-accent-yellow/5 border border-accent-yellow/20 rounded px-4 py-3">
                  <AlertTriangle size={14} />
                  <span>
                    No trades generated. Nesting requires aligned multi-timeframe signals.
                    Try lowering min depth to 1 or disabling alignment requirement.
                  </span>
                </div>
              )}
              <div className="grid grid-cols-4 gap-3">
                <ResultMetric label="TOTAL RETURN" value={`${(+result.total_return * 100).toFixed(2)}%`} positive={+result.total_return > 0} />
                <ResultMetric label="ANNUALIZED" value={`${(+result.annualized_return * 100).toFixed(2)}%`} positive={+result.annualized_return > 0} />
                <ResultMetric label="SHARPE RATIO" value={(+result.sharpe_ratio).toFixed(2)} positive={+result.sharpe_ratio > 1} />
                <ResultMetric label="SORTINO RATIO" value={(+result.sortino_ratio).toFixed(2)} positive={+result.sortino_ratio > 1} />
                <ResultMetric label="MAX DRAWDOWN" value={`${(+result.max_drawdown * 100).toFixed(2)}%`} positive={false} />
                <ResultMetric label="WIN RATE" value={`${(+result.win_rate * 100).toFixed(1)}%`} positive={+result.win_rate > 0.5} />
                <ResultMetric label="PROFIT FACTOR" value={(+result.profit_factor).toFixed(2)} positive={+result.profit_factor > 1} />
                <ResultMetric label="TOTAL TRADES" value={String(result.total_trades)} />
              </div>
            </div>
          </div>

          {result.trade_log.length > 0 && (
            <div className="card">
              <button
                className="card-header w-full flex items-center justify-between cursor-pointer"
                onClick={() => setShowLog(!showLog)}
              >
                <span>TRADE LOG ({result.trade_log.length})</span>
                {showLog ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {showLog && (
                <div className="p-3 overflow-x-auto">
                  <table className="w-full text-[10px]">
                    <thead>
                      <tr className="text-text-muted border-b border-bg-border/50">
                        <th className="py-1 px-2 text-left">TIME</th>
                        <th className="py-1 px-2 text-left">INST</th>
                        <th className="py-1 px-2 text-left">ACTION</th>
                        <th className="py-1 px-2 text-right">PRICE</th>
                        <th className="py-1 px-2 text-left">SIGNAL</th>
                        <th className="py-1 px-2 text-center">DEPTH</th>
                        <th className="py-1 px-2 text-center">ALIGNED</th>
                        <th className="py-1 px-2 text-left">LARGE</th>
                        <th className="py-1 px-2 text-left">MEDIUM</th>
                        <th className="py-1 px-2 text-left">PRECISE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trade_log.map((t, i) => (
                        <TradeRow key={i} trade={t} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ResultMetric({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="bg-bg-primary rounded px-3 py-3 border border-bg-border/50">
      <div className={cn('text-lg font-bold',
        positive === undefined ? 'text-text-primary' :
        positive ? 'text-accent-green' : 'text-accent-red'
      )}>{value}</div>
      <div className="text-[9px] text-text-muted tracking-wider mt-1">{label}</div>
    </div>
  )
}

function TradeRow({ trade }: { trade: TradeLogEntry }) {
  const isBuy = trade.action === 'BUY'
  return (
    <tr className="border-b border-bg-border/30 hover:bg-bg-secondary/50">
      <td className="py-1.5 px-2 text-text-muted">{trade.timestamp.slice(0, 16)}</td>
      <td className="py-1.5 px-2 font-medium">{trade.instrument}</td>
      <td className={cn('py-1.5 px-2 font-bold', isBuy ? 'text-accent-green' : 'text-accent-red')}>
        {trade.action}
      </td>
      <td className="py-1.5 px-2 text-right">{(+trade.price).toFixed(2)}</td>
      <td className="py-1.5 px-2">{trade.signal}</td>
      <td className="py-1.5 px-2 text-center">{trade.nesting_depth}</td>
      <td className="py-1.5 px-2 text-center">{trade.aligned ? 'Y' : 'N'}</td>
      <td className="py-1.5 px-2 text-text-dim">{trade.large ?? '-'}</td>
      <td className="py-1.5 px-2 text-text-dim">{trade.medium ?? '-'}</td>
      <td className="py-1.5 px-2 text-text-dim">{trade.precise ?? '-'}</td>
    </tr>
  )
}
