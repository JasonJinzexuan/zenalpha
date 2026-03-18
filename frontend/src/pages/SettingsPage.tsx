import { useState } from 'react'
import { useWatchlistStore } from '@/stores/watchlist'
import { useAuthStore } from '@/stores/auth'
import { ingestKLines } from '@/api/data'
import { Settings, Plus, X, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const { instruments, add, remove, reset } = useWatchlistStore()
  const { username } = useAuthStore()
  const [newSymbol, setNewSymbol] = useState('')
  const [syncing, setSyncing] = useState<string | null>(null)
  const [syncMsg, setSyncMsg] = useState('')

  function handleAdd() {
    const s = newSymbol.trim().toUpperCase()
    if (s && !instruments.includes(s)) {
      add(s)
      setNewSymbol('')
    }
  }

  async function handleSync(symbol: string) {
    setSyncing(symbol)
    setSyncMsg('')
    try {
      const res = await ingestKLines(symbol, '1d')
      setSyncMsg(`${symbol}: ingested ${res.records_written} bars`)
    } catch (e: any) {
      setSyncMsg(`${symbol}: ${e.message}`)
    } finally {
      setSyncing(null)
    }
  }

  async function handleSyncAll() {
    setSyncing('ALL')
    setSyncMsg('Syncing all...')
    let total = 0
    for (const sym of instruments) {
      try {
        const res = await ingestKLines(sym, '1d')
        total += res.records_written
      } catch { /* skip */ }
    }
    setSyncMsg(`Synced ${total} total bars across ${instruments.length} instruments`)
    setSyncing(null)
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center gap-3">
        <Settings size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">SETTINGS</h1>
      </div>

      {/* Account */}
      <div className="card">
        <div className="card-header">ACCOUNT</div>
        <div className="p-4">
          <div className="text-xs text-text-primary">{username || 'Unknown'}</div>
          <div className="text-[10px] text-text-muted mt-1">Active session</div>
        </div>
      </div>

      {/* Watchlist */}
      <div className="card">
        <div className="card-header">
          WATCHLIST
          <div className="flex items-center gap-2">
            <span className="tag">{instruments.length}</span>
            <button onClick={handleSyncAll} disabled={!!syncing} className="btn-ghost text-[10px]">
              <RefreshCw size={11} className={syncing === 'ALL' ? 'animate-spin' : ''} />
              SYNC ALL
            </button>
          </div>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <input
              className="input flex-1"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder="ADD SYMBOL..."
            />
            <button onClick={handleAdd} className="btn-primary">
              <Plus size={12} /> ADD
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {instruments.map((sym) => (
              <div key={sym} className="flex items-center gap-1 tag">
                <span className="text-text-primary">{sym}</span>
                <button
                  onClick={() => handleSync(sym)}
                  disabled={!!syncing}
                  className="text-text-muted hover:text-accent-cyan transition-colors"
                  title="Sync data"
                >
                  <RefreshCw size={9} className={syncing === sym ? 'animate-spin' : ''} />
                </button>
                <button onClick={() => remove(sym)} className="text-text-muted hover:text-accent-red transition-colors">
                  <X size={9} />
                </button>
              </div>
            ))}
          </div>

          {syncMsg && <div className="text-[10px] text-accent-cyan">{syncMsg}</div>}

          <button onClick={reset} className="text-[10px] text-text-muted hover:text-accent-red transition-colors cursor-pointer bg-transparent border-0">
            RESET TO DEFAULTS
          </button>
        </div>
      </div>
    </div>
  )
}
