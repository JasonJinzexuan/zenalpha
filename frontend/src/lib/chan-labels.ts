/** 缠论术语中文映射 */

import type { WalkState } from '@/types/chan'

/** 信号类型 B1→一买 etc */
export const SIGNAL_LABELS: Record<string, string> = {
  B1: '一买', B2: '二买', B3: '三买',
  S1: '一卖', S2: '二卖', S3: '三卖',
}

/** 走势状态 */
export const WALK_STATE_LABELS: Record<WalkState, { label: string; icon: string; color: string }> = {
  up_trend:          { label: '上涨趋势', icon: '↑', color: 'text-accent-red' },
  down_trend:        { label: '下跌趋势', icon: '↓', color: 'text-accent-green' },
  consolidation:     { label: '盘整',     icon: '─', color: 'text-accent-yellow' },
  c_extending:       { label: 'c段延伸',  icon: '⚡', color: 'text-accent-yellow' },
  top_divergence:    { label: '顶背驰',   icon: '⬇', color: 'text-accent-red' },
  bottom_divergence: { label: '底背驰',   icon: '⬆', color: 'text-accent-green' },
}

/** 信号类型中文显示 */
export function signalLabel(type: string): string {
  return SIGNAL_LABELS[type] || type
}

/** 买卖点简短标签（含原代号） */
export function signalTag(type: string): string {
  const cn = SIGNAL_LABELS[type]
  return cn ? `${cn}(${type})` : type
}

/** 结构术语 */
export const STRUCT = {
  fractal: '分型',
  stroke: '笔',
  segment: '线段',
  center: '中枢',
  divergence: '背驰',
  trend: '走势',
  kline: 'K线',
  macd: 'MACD',
} as const
