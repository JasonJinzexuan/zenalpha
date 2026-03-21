import { useState } from 'react'
import { Bell, Plus, X, Save } from 'lucide-react'
import { cn } from '@/lib/cn'

interface AlertCondition {
  id: string
  signalType: string
  minDepth: number
  requireAligned: boolean
  enabled: boolean
}

const DEFAULT_CONDITIONS: AlertCondition[] = [
  { id: '1', signalType: 'B1', minDepth: 2, requireAligned: true, enabled: true },
  { id: '2', signalType: 'S1', minDepth: 2, requireAligned: true, enabled: true },
  { id: '3', signalType: 'B3', minDepth: 1, requireAligned: false, enabled: false },
]

export default function NotificationsPage() {
  const [wssUrl, setWssUrl] = useState(localStorage.getItem('zen_wss_url') || '')
  const [conditions, setConditions] = useState<AlertCondition[]>(
    JSON.parse(localStorage.getItem('zen_alert_conditions') || 'null') || DEFAULT_CONDITIONS
  )
  const [saved, setSaved] = useState(false)

  function handleSave() {
    localStorage.setItem('zen_wss_url', wssUrl)
    localStorage.setItem('zen_alert_conditions', JSON.stringify(conditions))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  function addCondition() {
    setConditions(prev => [
      ...prev,
      { id: String(Date.now()), signalType: 'B1', minDepth: 1, requireAligned: false, enabled: true },
    ])
  }

  function removeCondition(id: string) {
    setConditions(prev => prev.filter(c => c.id !== id))
  }

  function updateCondition(id: string, patch: Partial<AlertCondition>) {
    setConditions(prev => prev.map(c => c.id === id ? { ...c, ...patch } : c))
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center gap-3">
        <Bell size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">通知配置</h1>
      </div>

      {/* WebSocket config */}
      <div className="card">
        <div className="card-header">WebSocket 推送配置</div>
        <div className="p-4 space-y-3">
          <div>
            <label className="text-[10px] text-text-muted tracking-wider block mb-1">WSS URL</label>
            <input
              className="input w-full"
              value={wssUrl}
              onChange={e => setWssUrl(e.target.value)}
              placeholder="wss://your-webhook-endpoint.example.com/ws"
            />
          </div>
          <div className="text-[9px] text-text-dim">
            配置 WebSocket 推送地址，当信号触发时将自动推送通知。留空则不推送。
          </div>
        </div>
      </div>

      {/* Alert conditions */}
      <div className="card">
        <div className="card-header">
          告警条件
          <button onClick={addCondition} className="btn-ghost text-[10px]">
            <Plus size={11} /> 添加
          </button>
        </div>
        <div className="p-4 space-y-3">
          {conditions.map(c => (
            <div key={c.id} className="flex items-center gap-3 p-3 bg-bg-primary rounded border border-bg-border/50">
              <input
                type="checkbox"
                checked={c.enabled}
                onChange={e => updateCondition(c.id, { enabled: e.target.checked })}
                className="accent-accent-cyan"
              />
              <select
                className="input w-20 text-[11px]"
                value={c.signalType}
                onChange={e => updateCondition(c.id, { signalType: e.target.value })}
              >
                {['B1', 'B2', 'B3', 'S1', 'S2', 'S3'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <div className="flex items-center gap-1.5 text-[10px] text-text-muted">
                <span>嵌套深度 ≥</span>
                <select
                  className="input w-14 text-[11px]"
                  value={c.minDepth}
                  onChange={e => updateCondition(c.id, { minDepth: +e.target.value })}
                >
                  {[1, 2, 3, 4].map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <label className="flex items-center gap-1 text-[10px] text-text-muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={c.requireAligned}
                  onChange={e => updateCondition(c.id, { requireAligned: e.target.checked })}
                  className="accent-accent-cyan"
                />
                方向一致
              </label>
              <button
                onClick={() => removeCondition(c.id)}
                className="ml-auto text-text-muted hover:text-accent-red transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          ))}

          {conditions.length === 0 && (
            <div className="text-center text-text-muted text-[11px] py-4">
              无告警条件。点击"添加"创建。
            </div>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button onClick={handleSave} className="btn-primary flex items-center gap-1.5">
          <Save size={12} />
          保存配置
        </button>
        {saved && <span className="text-[10px] text-accent-green">已保存 ✓</span>}
      </div>
    </div>
  )
}
