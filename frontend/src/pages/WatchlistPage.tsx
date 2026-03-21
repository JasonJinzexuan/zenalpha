import { useState } from 'react'
import { useWatchlistStore } from '@/stores/watchlist'
import { ingestKLines } from '@/api/data'
import { List, Plus, X, RefreshCw, Check, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

const ALL_TIMEFRAMES = ['1d', '1w', '30m', '5m']

interface IngestStatus {
  symbol: string
  status: 'pending' | 'ingesting' | 'done' | 'error'
  progress: string
  detail: string
}

export default function WatchlistPage() {
  const { instruments, add, remove, reset } = useWatchlistStore()
  const [newSymbol, setNewSymbol] = useState('')
  const [syncing, setSyncing] = useState<string | null>(null)
  const [syncMsg, setSyncMsg] = useState('')
  const [ingestStatuses, setIngestStatuses] = useState<IngestStatus[]>([])

  function handleAdd() {
    const s = newSymbol.trim().toUpperCase()
    if (s && !instruments.includes(s)) {
      add(s)
      setNewSymbol('')
      // Auto-trigger historical ingest
      triggerHistoricalIngest(s)
    }
  }

  async function triggerHistoricalIngest(symbol: string) {
    const status: IngestStatus = { symbol, status: 'pending', progress: '0/4', detail: '准备中...' }
    setIngestStatuses(prev => [...prev.filter(s => s.symbol !== symbol), status])

    let completed = 0
    let totalRecords = 0

    for (const tf of ALL_TIMEFRAMES) {
      setIngestStatuses(prev =>
        prev.map(s => s.symbol === symbol
          ? { ...s, status: 'ingesting', progress: `${completed}/${ALL_TIMEFRAMES.length}`, detail: `正在导入 ${tf} 数据...` }
          : s
        )
      )

      try {
        const res = await ingestKLines(symbol, tf, 500)
        totalRecords += res.records_written
        completed++
      } catch (err) {
        completed++
      }
    }

    setIngestStatuses(prev =>
      prev.map(s => s.symbol === symbol
        ? { ...s, status: 'done', progress: `${completed}/${ALL_TIMEFRAMES.length}`, detail: `完成: ${totalRecords} 条记录` }
        : s
      )
    )

    // Auto-clear after 10s
    setTimeout(() => {
      setIngestStatuses(prev => prev.filter(s => s.symbol !== symbol))
    }, 10000)
  }

  async function handleSync(symbol: string) {
    setSyncing(symbol)
    setSyncMsg('')
    let total = 0
    for (const tf of ALL_TIMEFRAMES) {
      try {
        const res = await ingestKLines(symbol, tf, 500)
        total += res.records_written
      } catch { /* skip */ }
    }
    setSyncMsg(`${symbol}: 同步完成, ${total} 条记录`)
    setSyncing(null)
  }

  async function handleSyncAll() {
    setSyncing('ALL')
    setSyncMsg('正在同步全部...')
    let total = 0
    for (const sym of instruments) {
      for (const tf of ALL_TIMEFRAMES) {
        try {
          const res = await ingestKLines(sym, tf, 500)
          total += res.records_written
        } catch { /* skip */ }
      }
    }
    setSyncMsg(`全部同步完成: ${total} 条记录 (${instruments.length} 标的 × ${ALL_TIMEFRAMES.length} 时间框架)`)
    setSyncing(null)
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center gap-3">
        <List size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">Watchlist 管理</h1>
      </div>

      {/* Add instrument */}
      <div className="card">
        <div className="card-header">
          添加标的
          <span className="text-[9px] text-text-dim">添加后自动导入6个月历史数据 (1d/1w/30m/5m)</span>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <input
              className="input flex-1"
              value={newSymbol}
              onChange={e => setNewSymbol(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
              placeholder="输入代码 (如 AAPL)"
            />
            <button onClick={handleAdd} className="btn-primary">
              <Plus size={12} /> 添加
            </button>
          </div>

          {/* Ingest progress */}
          {ingestStatuses.map(s => (
            <div key={s.symbol} className={cn(
              'flex items-center gap-3 px-3 py-2 rounded border text-[10px]',
              s.status === 'done' ? 'border-accent-green/20 bg-accent-green/5' :
              s.status === 'error' ? 'border-accent-red/20 bg-accent-red/5' :
              'border-accent-cyan/20 bg-accent-cyan/5'
            )}>
              {s.status === 'ingesting' && <Loader2 size={12} className="text-accent-cyan animate-spin" />}
              {s.status === 'done' && <Check size={12} className="text-accent-green" />}
              {s.status === 'error' && <AlertCircle size={12} className="text-accent-red" />}
              <span className="font-bold text-text-primary">{s.symbol}</span>
              <span className="text-text-muted">[{s.progress}]</span>
              <span className="text-text-dim">{s.detail}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Current watchlist */}
      <div className="card">
        <div className="card-header">
          当前 Watchlist
          <div className="flex items-center gap-2">
            <span className="tag">{instruments.length}</span>
            <button onClick={handleSyncAll} disabled={!!syncing} className="btn-ghost text-[10px]">
              <RefreshCw size={11} className={syncing === 'ALL' ? 'animate-spin' : ''} />
              全部同步
            </button>
          </div>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {instruments.map(sym => (
              <div key={sym} className="flex items-center justify-between px-3 py-2 bg-bg-primary rounded border border-bg-border/50">
                <span className="text-xs font-bold text-text-primary font-mono">{sym}</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSync(sym)}
                    disabled={!!syncing}
                    className="text-text-muted hover:text-accent-cyan transition-colors"
                    title="同步数据"
                  >
                    <RefreshCw size={11} className={syncing === sym ? 'animate-spin' : ''} />
                  </button>
                  <button onClick={() => remove(sym)} className="text-text-muted hover:text-accent-red transition-colors" title="移除">
                    <X size={11} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {syncMsg && <div className="text-[10px] text-accent-cyan">{syncMsg}</div>}

          <button
            onClick={reset}
            className="text-[10px] text-text-muted hover:text-accent-red transition-colors cursor-pointer bg-transparent border-0"
          >
            恢复默认 Watchlist
          </button>
        </div>
      </div>
    </div>
  )
}
