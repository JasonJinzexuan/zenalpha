import { useState } from 'react'
import { runBacktest } from '@/api/agent'
import { getKLines } from '@/api/data'
import { cn } from '@/lib/cn'
import type { BacktestResponse } from '@/types/api'
import { FlaskConical, Play } from 'lucide-react'

export default function BacktestPage() {
  const [instruments, setInstruments] = useState('AAPL,MSFT,NVDA')
  const [initialCash, setInitialCash] = useState('1000000')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResponse | null>(null)
  const [error, setError] = useState('')

  async function handleRun() {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const symbols = instruments.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean)
      const klineMap: Record<string, any[]> = {}

      for (const sym of symbols) {
        const klines = await getKLines(sym, '1d', 250)
        klineMap[sym] = klines.map((k) => ({
          timestamp: k.timestamp,
          open: String(k.open), high: String(k.high),
          low: String(k.low), close: String(k.close),
          volume: k.volume,
        }))
      }

      const res = await runBacktest({ instruments: klineMap, initial_cash: initialCash })
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
        <h1 className="text-lg font-semibold tracking-[2px]">BACKTEST LAB</h1>
      </div>

      {/* Config */}
      <div className="card">
        <div className="card-header">CONFIGURATION</div>
        <div className="p-4 space-y-3">
          <div>
            <label className="text-[10px] text-text-muted tracking-wider block mb-1">INSTRUMENTS (comma-separated)</label>
            <input className="input w-full" value={instruments} onChange={(e) => setInstruments(e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-text-muted tracking-wider block mb-1">INITIAL CAPITAL</label>
            <input className="input w-48" value={initialCash} onChange={(e) => setInitialCash(e.target.value)} />
          </div>
          <button onClick={handleRun} disabled={loading} className="btn-primary">
            <Play size={12} />
            {loading ? 'RUNNING...' : 'RUN BACKTEST'}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-accent-red text-[11px] bg-accent-red/5 border border-accent-red/20 rounded px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <div className="card">
          <div className="card-header">RESULTS</div>
          <div className="p-4">
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
