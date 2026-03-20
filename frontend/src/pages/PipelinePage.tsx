import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, ChevronDown, ChevronRight, CheckCircle2,
  XCircle, Clock, Loader2, AlertTriangle, Zap,
} from 'lucide-react'
import { triggerPipeline, getPipelineStatus } from '@/api/agent'
import { useWatchlistStore } from '@/stores/watchlist'
import { cn } from '@/lib/cn'
import type { PipelineItem, PipelineStage } from '@/types/chan'

const STAGE_LABELS: Record<string, string> = {
  deterministic_l0_l2: 'L0-L2 K线/分型/笔',
  segment: 'L3 线段',
  structure: 'L4-L5 中枢+走势',
  divergence: 'L6 背驰',
  signal: 'L7 信号',
  nesting: 'L8 区间套 (Tool Use)',
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { label: string; cls: string }> = {
    idle: { label: '待触发', cls: 'text-text-muted bg-bg-primary' },
    pending: { label: '排队中', cls: 'text-accent-yellow bg-accent-yellow/10' },
    running: { label: '分析中', cls: 'text-accent-cyan bg-accent-cyan/10 animate-pulse' },
    done: { label: '完成', cls: 'text-accent-green bg-accent-green/10' },
    error: { label: '失败', cls: 'text-accent-red bg-accent-red/10' },
  }
  const c = cfg[status] || cfg.idle
  return <span className={cn('text-[9px] px-1.5 py-0.5 rounded font-semibold tracking-wider', c.cls)}>{c.label}</span>
}

function StageIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle2 size={12} className="text-accent-green shrink-0" />
  if (status === 'error') return <XCircle size={12} className="text-accent-red shrink-0" />
  if (status === 'skipped') return <AlertTriangle size={12} className="text-accent-yellow shrink-0" />
  return <Clock size={12} className="text-text-muted shrink-0" />
}

function JsonBlock({ data, label }: { data: unknown; label: string }) {
  const [open, setOpen] = useState(false)
  const json = JSON.stringify(data, null, 2)
  const isEmpty = !data || (typeof data === 'object' && Object.keys(data as object).length === 0)
  if (isEmpty) return null

  return (
    <div className="mt-1.5">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-[9px] text-text-dim hover:text-accent-cyan transition-colors">
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {label}
      </button>
      {open && (
        <pre className="mt-1 p-2 rounded bg-bg-primary/80 border border-bg-border text-[9px] text-text-secondary overflow-x-auto max-h-[300px] overflow-y-auto leading-relaxed">
          {json}
        </pre>
      )}
    </div>
  )
}

function StageMiniBar({ stages, totalMs }: { stages: PipelineStage[]; totalMs: number }) {
  if (!stages.length || !totalMs) return null
  const colors: Record<string, string> = {
    deterministic_l0_l2: 'bg-accent-cyan/60',
    segment: 'bg-accent-green/60',
    structure: 'bg-accent-yellow/60',
    divergence: 'bg-accent-purple/60',
    signal: 'bg-accent-red/60',
    nesting: 'bg-accent-cyan/40',
  }
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden bg-bg-primary border border-bg-border/50 w-full mt-1.5">
      {stages.map((s) => {
        const pct = (s.duration_ms / totalMs) * 100
        if (pct < 1) return null
        return <div key={s.name} className={colors[s.name] || 'bg-text-muted/30'} style={{ width: `${pct}%` }} title={`${STAGE_LABELS[s.name] || s.name}: ${s.duration_ms}ms`} />
      })}
    </div>
  )
}

function StageDetail({ stage }: { stage: PipelineStage }) {
  const [expanded, setExpanded] = useState(false)
  const label = STAGE_LABELS[stage.name] || stage.name

  return (
    <div className="border-b border-bg-border/50 last:border-0">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg-hover/30 transition-colors">
        <StageIcon status={stage.status} />
        <span className="text-[10px] text-text-primary flex-1">{label}</span>
        <span className="text-[9px] text-text-dim font-mono">
          {stage.duration_ms >= 1000 ? `${(stage.duration_ms / 1000).toFixed(1)}s` : `${stage.duration_ms}ms`}
        </span>
        {expanded ? <ChevronDown size={10} className="text-text-muted" /> : <ChevronRight size={10} className="text-text-muted" />}
      </button>
      {expanded && (
        <div className="px-3 pb-2">
          {stage.error && <div className="text-[9px] text-accent-red bg-accent-red/10 rounded p-1.5 mb-1">{stage.error}</div>}
          <JsonBlock data={stage.input_summary} label="INPUT" />
          <JsonBlock data={stage.output_summary} label="OUTPUT" />
        </div>
      )}
    </div>
  )
}

function InstrumentCard({ item }: { item: PipelineItem }) {
  const [expanded, setExpanded] = useState(false)
  const isDone = item.status === 'done'
  const isError = item.status === 'error'

  return (
    <div className={cn('card', isError && 'border-accent-red/30', isDone && item.signals.length > 0 && 'border-accent-green/30')}>
      {/* Summary row */}
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-bg-hover/30 transition-colors">
        <span className="text-xs font-mono font-bold text-text-primary w-14">{item.instrument}</span>
        <StatusBadge status={item.status} />

        {isDone && (
          <div className="flex items-center gap-3 flex-1 text-[10px] text-text-dim">
            <span>{item.stages.length} stages</span>
            <span>{item.segments.length} 线段</span>
            <span>{item.centers.length} 中枢</span>
            <span className={item.signals.length > 0 ? 'text-accent-green font-semibold' : ''}>{item.signals.length} 信号</span>
            {item.trend && <span className="text-accent-cyan">{(item.trend as Record<string, string>).classification || ''}</span>}
            {item.divergence && <span className="text-accent-red font-semibold">有背驰</span>}
            {item.nesting && (
              <span className="text-accent-purple">
                套{(item.nesting as any).nesting_depth || 0}层
                {(item.nesting as any).direction_aligned ? ' ✓' : ''}
              </span>
            )}
            <span className="ml-auto font-mono">{(item.total_duration_ms / 1000).toFixed(1)}s</span>
          </div>
        )}

        {isError && item.errors.length > 0 && (
          <span className="text-[10px] text-accent-red flex-1 truncate">{item.errors[0]}</span>
        )}

        {(item.status === 'running' || item.status === 'pending') && (
          <Loader2 size={14} className="text-accent-cyan animate-spin ml-auto" />
        )}

        <ChevronDown size={14} className={cn('text-text-muted transition-transform shrink-0', expanded && 'rotate-180')} />
      </button>

      {/* Timeline mini bar */}
      {isDone && (
        <div className="px-4 pb-2">
          <StageMiniBar stages={item.stages} totalMs={item.total_duration_ms} />
        </div>
      )}

      {/* Expanded detail */}
      {expanded && isDone && (
        <div className="border-t border-bg-border">
          {/* Stages */}
          <div className="bg-bg-primary/30">
            {item.stages.map((s) => <StageDetail key={s.name} stage={s} />)}
          </div>

          {/* Final outputs */}
          <div className="px-4 py-3 border-t border-bg-border space-y-1">
            <div className="text-[9px] text-text-muted tracking-wider mb-2">FINAL OUTPUT</div>
            <JsonBlock data={item.signals} label={`SIGNALS (${item.signals.length})`} />
            <JsonBlock data={item.segments} label={`SEGMENTS (${item.segments.length})`} />
            <JsonBlock data={item.centers} label={`CENTERS (${item.centers.length})`} />
            <JsonBlock data={item.trend} label="TREND" />
            <JsonBlock data={item.divergence} label="DIVERGENCE" />
            <JsonBlock data={item.nesting} label="NESTING" />
            {item.nesting && (item.nesting as any).tool_calls && (
              <div className="mt-2">
                <div className="text-[9px] text-accent-purple tracking-wider mb-1 flex items-center gap-1">
                  <Zap size={10} className="text-accent-purple" />
                  TOOL CALLS ({((item.nesting as any).tool_calls || []).length})
                </div>
                <div className="space-y-0.5">
                  {((item.nesting as any).tool_calls || []).map((tc: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-[9px] py-0.5 px-2 bg-bg-primary/30 rounded">
                      <span className="text-text-muted w-3">#{tc.iteration}</span>
                      <span className="text-accent-cyan font-mono">{tc.tool}</span>
                      <span className="text-text-dim truncate">{JSON.stringify(tc.args)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {expanded && isError && item.errors.length > 0 && (
        <div className="border-t border-bg-border px-4 py-3">
          {item.errors.map((e, i) => <div key={i} className="text-[10px] text-accent-red">{e}</div>)}
        </div>
      )}
    </div>
  )
}

export default function PipelinePage() {
  const { instruments: watchlist } = useWatchlistStore()
  const [level, setLevel] = useState('1d')
  const [items, setItems] = useState<PipelineItem[]>([])
  const [loading, setLoading] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeInstrumentsRef = useRef<string[]>([])

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const poll = useCallback(async () => {
    if (!activeInstrumentsRef.current.length) return
    try {
      const data = await getPipelineStatus(activeInstrumentsRef.current, level)
      setItems(data)
      const allDone = data.every((d) => d.status === 'done' || d.status === 'error' || d.status === 'idle')
      if (allDone) stopPolling()
    } catch {
      // keep polling
    }
  }, [level, stopPolling])

  // Load existing status on mount
  useEffect(() => {
    activeInstrumentsRef.current = watchlist
    getPipelineStatus(watchlist, level).then(setItems).catch(() => {})
    return stopPolling
  }, [watchlist, level, stopPolling])

  async function triggerAll() {
    setLoading(true)
    activeInstrumentsRef.current = watchlist
    try {
      await triggerPipeline(watchlist, level)
      // Start polling
      stopPolling()
      poll()
      pollingRef.current = setInterval(poll, 3000)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const running = items.filter((i) => i.status === 'running' || i.status === 'pending').length
  const done = items.filter((i) => i.status === 'done').length
  const totalSignals = items.reduce((sum, i) => sum + (i.signals?.length || 0), 0)

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-sm font-bold text-text-primary tracking-wide flex items-center gap-2">
            <Zap size={16} className="text-accent-cyan" />
            LLM PIPELINE
          </h1>
          <p className="text-[10px] text-text-muted mt-0.5">
            LangGraph 多Agent缠论分析 + Tool Use — Watchlist {watchlist.length} 标的
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select className="input w-20 text-[11px]" value={level} onChange={(e) => setLevel(e.target.value)}>
            {['1d', '1w', '30m', '5m'].map((lv) => <option key={lv} value={lv}>{lv}</option>)}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={triggerAll} disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            一键分析
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {items.length > 0 && (
        <div className="flex items-center gap-5 text-[10px]">
          {running > 0 && <span className="text-accent-cyan animate-pulse">分析中: {running}</span>}
          {done > 0 && <span className="text-accent-green">完成: {done}/{items.length}</span>}
          {totalSignals > 0 && <span className="text-accent-yellow font-semibold">信号: {totalSignals}</span>}
        </div>
      )}

      {/* Instrument cards */}
      <div className="space-y-2">
        {items.length > 0
          ? items.map((item) => <InstrumentCard key={item.instrument} item={item} />)
          : watchlist.map((sym) => (
              <div key={sym} className="card px-4 py-3 flex items-center gap-3">
                <span className="text-xs font-mono font-bold text-text-primary w-14">{sym}</span>
                <StatusBadge status="idle" />
                <span className="text-[10px] text-text-muted">点击「一键分析」开始</span>
              </div>
            ))
        }
      </div>
    </div>
  )
}
