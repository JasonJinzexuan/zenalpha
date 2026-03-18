import { useState } from 'react'
import { cn } from '@/lib/cn'
import { signalTag, STRUCT } from '@/lib/chan-labels'
import { ClipboardCheck, AlertCircle, ChevronRight, X } from 'lucide-react'

interface ReviewRecord {
  id: number
  instrument: string
  level: string
  type: string
  date: string
  price: number
  correct: boolean | null  // null = pending
  reasoning: string
  mae?: number
  mfe?: number
  failure?: string
  lesson?: string
  structureSnapshot?: {
    strokes: number
    segments: number
    centers: number
    divergences: number
    walkState: string
  }
}

const REVIEW_RECORDS: ReviewRecord[] = [
  // Correct
  { id: 1, instrument: 'AAPL', level: '日线', type: 'B1', date: '2026-03-05', price: 252.30, correct: true,
    reasoning: '底背驰确认，a段MACD面积45.2 > c段38.1（差15.7%），DIF同步背驰',
    mfe: 5.2,
    structureSnapshot: { strokes: 12, segments: 3, centers: 2, divergences: 1, walkState: '底背驰' } },
  { id: 2, instrument: 'MSFT', level: '30分', type: 'B2', date: '2026-03-08', price: 418.50, correct: true,
    reasoning: '一买后回抽不破中枢ZD，二买确认。成交量萎缩确认回抽力度弱',
    mfe: 3.8,
    structureSnapshot: { strokes: 18, segments: 4, centers: 2, divergences: 0, walkState: '上涨趋势' } },
  { id: 3, instrument: 'NVDA', level: '日线', type: 'B2', date: '2026-03-10', price: 845.00, correct: true,
    reasoning: '日线一买后回踩确认，未破前低，二买成立',
    mfe: 4.1,
    structureSnapshot: { strokes: 8, segments: 2, centers: 1, divergences: 0, walkState: '上涨趋势' } },
  { id: 4, instrument: 'META', level: '30分', type: 'B3', date: '2026-03-12', price: 580.20, correct: true,
    reasoning: '回抽中枢上沿不进入，三买成立',
    mfe: 2.9,
    structureSnapshot: { strokes: 22, segments: 5, centers: 3, divergences: 0, walkState: 'c段延伸' } },
  { id: 5, instrument: 'JPM', level: '日线', type: 'S1', date: '2026-03-14', price: 230.00, correct: true,
    reasoning: '顶背驰确认，a段面积大于c段，卖出信号成立',
    mfe: 3.0,
    structureSnapshot: { strokes: 10, segments: 3, centers: 2, divergences: 1, walkState: '顶背驰' } },

  // Incorrect
  { id: 10, instrument: 'AMD', level: '30分', type: 'B1', date: '2026-03-11', price: 165.30, correct: false,
    reasoning: '底背驰确认，a段MACD面积45.2 > c段38.1（差15.7%）',
    mae: 3.2, mfe: 0.8,
    failure: 'FOMC决议后跳空低开击穿DD',
    lesson: '事件驱动的价格跳空不是自然趋势衰竭',
    structureSnapshot: { strokes: 14, segments: 3, centers: 1, divergences: 1, walkState: '底背驰' } },
  { id: 11, instrument: 'AVGO', level: '30分', type: 'B1', date: '2026-03-12', price: 1720.00, correct: false,
    reasoning: '盘整底背驰，面积比12%',
    mae: 2.8, mfe: 0.3,
    failure: 'NVDA财报引发板块集体抛售',
    lesson: '财报季关联板块风险',
    structureSnapshot: { strokes: 16, segments: 4, centers: 2, divergences: 1, walkState: '盘整' } },
  { id: 12, instrument: 'TSLA', level: '5分', type: 'B3', date: '2026-03-13', price: 248.50, correct: false,
    reasoning: '三买回抽中枢上沿不进入',
    mae: 4.1, mfe: 0.5,
    failure: '价格击穿中枢，三买无效',
    lesson: '波动大的股票三买需要更高置信阈值',
    structureSnapshot: { strokes: 30, segments: 6, centers: 3, divergences: 0, walkState: 'c段延伸' } },

  // Pending
  { id: 20, instrument: 'UNH', level: '日线', type: 'B2', date: '2026-03-17', price: 510.00, correct: null,
    reasoning: '一买后回踩确认中，等待收盘确认',
    structureSnapshot: { strokes: 9, segments: 2, centers: 1, divergences: 0, walkState: '上涨趋势' } },
  { id: 21, instrument: 'V', level: '30分', type: 'S2', date: '2026-03-17', price: 320.50, correct: null,
    reasoning: '一卖后反弹不过中枢，二卖待确认',
    structureSnapshot: { strokes: 20, segments: 4, centers: 2, divergences: 1, walkState: '顶背驰' } },
]

const INSIGHTS = [
  {
    title: '科技股30分钟一买准确率仅45%（平均67%）',
    analysis: '本周FOMC前波动率导致MACD失真',
    suggestion: '当VIX>25时，自动降低30分钟一买置信度0.15',
  },
  {
    title: '波动大的股票三买假阳性率偏高',
    analysis: '流动性不足导致回抽判断不精确',
    suggestion: '对高波动股票，三买信号得分乘以0.7',
  },
]

export default function ReviewPage() {
  const [selectedRecord, setSelectedRecord] = useState<ReviewRecord | null>(null)

  const correctRecords = REVIEW_RECORDS.filter(r => r.correct === true)
  const incorrectRecords = REVIEW_RECORDS.filter(r => r.correct === false)
  const pendingRecords = REVIEW_RECORDS.filter(r => r.correct === null)
  const total = REVIEW_RECORDS.length
  const accuracy = total > 0 ? ((correctRecords.length / (correctRecords.length + incorrectRecords.length)) * 100).toFixed(0) : '0'

  const byType = ['B1', 'B2', 'B3', 'S1', 'S2', 'S3'].map(type => {
    const ofType = REVIEW_RECORDS.filter(r => r.type === type && r.correct !== null)
    const correct = ofType.filter(r => r.correct === true).length
    return { type, correct, total: ofType.length }
  }).filter(s => s.total > 0)

  const byLevel = ['周线', '日线', '30分', '5分'].map(level => {
    const ofLevel = REVIEW_RECORDS.filter(r => r.level === level && r.correct !== null)
    const correct = ofLevel.filter(r => r.correct === true).length
    return { level, correct, total: ofLevel.length }
  }).filter(s => s.total > 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <ClipboardCheck size={18} className="text-accent-cyan" />
        <h1 className="text-lg font-semibold tracking-[2px]">信号回顾</h1>
        <span className="text-text-muted text-[10px] tracking-wider">2026-03-05 ~ 2026-03-17</span>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-3">
        <SummaryCard label="总计" value={total} color="text-accent-cyan" />
        <SummaryCard label="正确" value={correctRecords.length} sub={`${accuracy}%`} color="text-accent-green" />
        <SummaryCard label="错误" value={incorrectRecords.length} color="text-accent-red" />
        <SummaryCard label="待定" value={pendingRecords.length} color="text-accent-yellow" />
      </div>

      {/* By type + By level */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <div className="card-header">按买卖点类型</div>
          <div className="p-4 space-y-2.5">
            {byType.map(s => {
              const pct = s.total > 0 ? (s.correct / s.total) * 100 : 0
              const good = pct >= 70
              return (
                <div key={s.type} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn('tag font-semibold', s.type.startsWith('B') ? 'tag-green' : 'tag-red')}>{signalTag(s.type)}</span>
                    <span className="text-[10px] text-text-dim">{s.correct}/{s.total}</span>
                  </div>
                  <div className="flex items-center gap-2 w-36">
                    <div className="flex-1 h-2 bg-bg-border rounded-full overflow-hidden">
                      <div className={cn('h-full rounded-full transition-all', good ? 'bg-accent-green' : 'bg-accent-yellow')} style={{ width: `${pct}%` }} />
                    </div>
                    <span className={cn('text-[10px] font-medium w-12 text-right', good ? 'text-accent-green' : 'text-accent-yellow')}>
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-header">按周期</div>
          <div className="p-4 space-y-2.5">
            {byLevel.map(s => {
              const pct = s.total > 0 ? (s.correct / s.total) * 100 : 0
              const good = pct >= 70
              return (
                <div key={s.level} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="tag tag-cyan">{s.level}</span>
                    <span className="text-[10px] text-text-dim">{s.correct}/{s.total}</span>
                  </div>
                  <div className="flex items-center gap-2 w-36">
                    <div className="flex-1 h-2 bg-bg-border rounded-full overflow-hidden">
                      <div className={cn('h-full rounded-full transition-all', good ? 'bg-accent-purple' : 'bg-accent-yellow')} style={{ width: `${pct}%` }} />
                    </div>
                    <span className={cn('text-[10px] font-medium w-12 text-right', good ? 'text-accent-purple' : 'text-accent-yellow')}>
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Agent Insights */}
      <div className="card border-accent-cyan/20">
        <div className="card-header">信号复盘 — 本周洞察</div>
        <div className="p-4 space-y-3">
          {INSIGHTS.map((ins, i) => (
            <div key={i} className="p-3 bg-bg-primary rounded border border-bg-border/50 space-y-1.5">
              <div className="text-[11px] text-text-primary font-semibold">{i + 1}. {ins.title}</div>
              <div className="text-[10px] text-text-dim">分析: {ins.analysis}</div>
              <div className="text-[10px] text-accent-cyan">建议: {ins.suggestion}</div>
            </div>
          ))}
        </div>
      </div>

      {/* All records — clickable */}
      <RecordTable title="正确记录" records={correctRecords} onSelect={setSelectedRecord} tagClass="tag-green" tagLabel="正确" />
      <RecordTable title="错误记录" records={incorrectRecords} onSelect={setSelectedRecord} tagClass="tag-red" tagLabel="错误" borderClass="border-accent-red/20" />
      <RecordTable title="待定记录" records={pendingRecords} onSelect={setSelectedRecord} tagClass="tag-yellow" tagLabel="待定" />

      {/* Detail modal */}
      {selectedRecord && (
        <RecordDetail record={selectedRecord} onClose={() => setSelectedRecord(null)} />
      )}
    </div>
  )
}

function RecordTable({ title, records, onSelect, tagClass, tagLabel, borderClass = '' }: {
  title: string
  records: ReviewRecord[]
  onSelect: (r: ReviewRecord) => void
  tagClass: string
  tagLabel: string
  borderClass?: string
}) {
  if (records.length === 0) return null
  return (
    <div className={cn('card', borderClass)}>
      <div className="card-header">
        {title}
        <span className={cn('tag', tagClass)}>{records.length}</span>
      </div>
      <div className="divide-y divide-bg-border">
        {records.map(r => (
          <div
            key={r.id}
            className="px-4 py-3 flex items-center justify-between hover:bg-bg-hover cursor-pointer transition-colors"
            onClick={() => onSelect(r)}
          >
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-text-primary">{r.instrument}</span>
              <span className={cn('tag font-semibold', r.type.startsWith('B') ? 'tag-green' : 'tag-red')}>{signalTag(r.type)}</span>
              <span className="tag">{r.level}</span>
              <span className="text-[10px] text-text-muted">{r.date}</span>
              <span className="text-[10px] text-text-dim">@ ${r.price}</span>
            </div>
            <div className="flex items-center gap-3">
              {r.mae !== undefined && (
                <span className="text-[10px] text-text-muted">
                  MAE: {r.mae}% | MFE: {r.mfe}%
                </span>
              )}
              {r.mfe !== undefined && r.mae === undefined && (
                <span className="text-[10px] text-accent-green">MFE: {r.mfe}%</span>
              )}
              <span className={cn('tag font-semibold', tagClass)}>{tagLabel}</span>
              <ChevronRight size={12} className="text-text-muted" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RecordDetail({ record: r, onClose }: { record: ReviewRecord; onClose: () => void }) {
  const isCorrect = r.correct === true
  const isIncorrect = r.correct === false

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-bg-card border border-bg-border rounded-lg w-full max-w-xl mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-5 py-4 border-b border-bg-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-text-primary">{r.instrument}</span>
            <span className={cn('tag font-semibold', r.type.startsWith('B') ? 'tag-green' : 'tag-red')}>{signalTag(r.type)}</span>
            <span className="tag">{r.level}</span>
            <span className={cn('tag font-semibold', isCorrect ? 'tag-green' : isIncorrect ? 'tag-red' : 'tag-yellow')}>
              {isCorrect ? '正确' : isIncorrect ? '错误' : '待定'}
            </span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-bg-hover rounded transition-colors text-text-muted hover:text-text-primary">
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Basic info */}
          <div className="grid grid-cols-3 gap-3 text-[11px]">
            <div>
              <span className="text-text-muted">日期</span>
              <div className="text-text-primary font-medium">{r.date}</div>
            </div>
            <div>
              <span className="text-text-muted">价格</span>
              <div className="text-text-primary font-medium">${r.price}</div>
            </div>
            <div>
              <span className="text-text-muted">级别</span>
              <div className="text-text-primary font-medium">{r.level}</div>
            </div>
          </div>

          {/* Reasoning */}
          <div className="bg-bg-primary rounded p-3 border border-bg-border/50">
            <div className="text-[10px] text-text-muted tracking-wider mb-1">信号推理</div>
            <div className="text-[11px] text-text-primary leading-relaxed">{r.reasoning}</div>
          </div>

          {/* Structure snapshot */}
          {r.structureSnapshot && (
            <div>
              <div className="text-[10px] text-text-muted tracking-wider mb-2">信号触发时结构快照</div>
              <div className="grid grid-cols-5 gap-2">
                <SnapshotBox label={STRUCT.stroke} value={r.structureSnapshot.strokes} color="text-accent-blue" />
                <SnapshotBox label={STRUCT.segment} value={r.structureSnapshot.segments} color="text-accent-purple" />
                <SnapshotBox label={STRUCT.center} value={r.structureSnapshot.centers} color="text-accent-yellow" />
                <SnapshotBox label={STRUCT.divergence} value={r.structureSnapshot.divergences} color={r.structureSnapshot.divergences > 0 ? 'text-accent-red' : ''} />
                <div className="bg-bg-primary rounded px-2 py-1.5 border border-bg-border/50">
                  <div className="text-[10px] font-semibold text-text-primary">{r.structureSnapshot.walkState}</div>
                  <div className="text-[8px] text-text-muted">走势</div>
                </div>
              </div>
            </div>
          )}

          {/* MAE/MFE */}
          {(r.mae !== undefined || r.mfe !== undefined) && (
            <div className="grid grid-cols-2 gap-3">
              {r.mae !== undefined && (
                <div className="bg-accent-red/5 border border-accent-red/20 rounded p-3">
                  <div className="text-[10px] text-accent-red font-semibold">最大不利偏移 (MAE)</div>
                  <div className="text-lg font-bold text-accent-red">{r.mae}%</div>
                  <div className="text-[10px] text-text-muted">入场后最大亏损幅度</div>
                </div>
              )}
              {r.mfe !== undefined && (
                <div className="bg-accent-green/5 border border-accent-green/20 rounded p-3">
                  <div className="text-[10px] text-accent-green font-semibold">最大有利偏移 (MFE)</div>
                  <div className="text-lg font-bold text-accent-green">{r.mfe}%</div>
                  <div className="text-[10px] text-text-muted">入场后最大盈利幅度</div>
                </div>
              )}
            </div>
          )}

          {/* Failure analysis (incorrect only) */}
          {isIncorrect && r.failure && (
            <div className="bg-accent-red/5 border border-accent-red/20 rounded p-3 space-y-2">
              <div className="flex items-center gap-2">
                <AlertCircle size={12} className="text-accent-red" />
                <span className="text-[10px] text-accent-red font-semibold">失败原因</span>
              </div>
              <div className="text-[11px] text-text-primary">{r.failure}</div>
              {r.mae !== undefined && r.mfe !== undefined && (
                <div className={cn('text-[10px] font-medium', r.mae > r.mfe * 2 ? 'text-accent-red' : 'text-accent-yellow')}>
                  {r.mae > r.mfe * 2 ? '风险收益比差' : '边际'}
                </div>
              )}
            </div>
          )}

          {/* Lesson */}
          {r.lesson && (
            <div className="bg-accent-yellow/5 border border-accent-yellow/20 rounded p-3">
              <div className="text-[10px] text-accent-yellow font-semibold mb-1">经验教训</div>
              <div className="text-[11px] text-text-primary">{r.lesson}</div>
            </div>
          )}
        </div>
      </div>
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

function SummaryCard({ label, value, sub, color }: { label: string; value: number; sub?: string; color: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="flex items-baseline gap-2">
        <span className={cn('text-2xl font-bold', color)}>{value}</span>
        {sub && <span className="text-[10px] text-text-muted">{sub}</span>}
      </div>
      <div className="text-[9px] text-text-muted tracking-wider mt-1">{label}</div>
    </div>
  )
}
