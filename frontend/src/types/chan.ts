/** Core Chan Theory domain types — matches backend API snake_case */

export type TimeFrame = '1m' | '5m' | '30m' | '1h' | '1d' | '1w' | '1M'
export type TrendDirection = 'up' | 'down' | 'consolidation'
export type SignalType = 'B1' | 'B2' | 'B3' | 'S1' | 'S2' | 'S3'

export type WalkState =
  | 'up_trend'
  | 'down_trend'
  | 'consolidation'
  | 'c_extending'
  | 'top_divergence'
  | 'bottom_divergence'

export interface KLineData {
  timestamp: string
  open: number | string
  high: number | string
  low: number | string
  close: number | string
  volume: number
}

// ── Structural data from backend ──

export interface FractalData {
  type: 'top' | 'bottom'
  timestamp: string
  price: string
  kline_index: number
}

export interface StrokeData {
  direction: 'up' | 'down'
  start_index: number
  end_index: number
  start_price: string
  end_price: string
  start_time: string
  end_time: string
  kline_count: number
  macd_area: string
}

export interface SegmentData {
  direction: 'up' | 'down'
  start_index: number
  end_index: number
  start_time: string
  end_time: string
  high: string
  low: string
  stroke_count: number
  termination_type: 'first' | 'second'
}

export interface CenterData {
  zg: string
  zd: string
  gg: string
  dd: string
  start_time: string
  end_time: string
  extension_count: number
}

export interface DivergenceData {
  type: 'trend' | 'consolidation'
  a_macd_area: string
  c_macd_area: string
  a_dif_peak: string
  c_dif_peak: string
  area_ratio: string
  strength: string
}

export interface MACDData {
  dif: string
  dea: string
  histogram: string
}

export interface TrendData {
  classification: 'up_trend' | 'down_trend' | 'consolidation'
  center_count: number
  has_segment_c: boolean
  walk_state: WalkState
}

// ── Signal (backend returns snake_case) ──

export interface Signal {
  signal_type: string
  signalType?: SignalType  // frontend alias
  level: string
  instrument: string
  timestamp: string
  price: string
  strength: string
  source_lesson: string
  reasoning: string
  confidence?: number
}

/** Helper to get signal type string from either format */
export function getSignalType(s: Signal): string {
  return s.signal_type || s.signalType || ''
}

export function isBuySignal(s: Signal): boolean {
  return getSignalType(s).startsWith('B')
}

// ── Analysis Result (from /analyze and /scan) ──

export interface AnalysisResult {
  instrument: string
  level: string
  kline_count: number
  fractal_count: number
  stroke_count: number
  segment_count: number
  center_count: number
  divergence_count: number
  signals: Signal[]
  fractals: FractalData[]
  strokes: StrokeData[]
  segments: SegmentData[]
  centers: CenterData[]
  divergences: DivergenceData[]
  macd_values: MACDData[]
  trend: TrendData | null
}

export type ScanResultItem = AnalysisResult

// ── Multi-level status (computed on frontend) ──

export interface MultiLevelStatus {
  instrument: string
  levels: Partial<Record<TimeFrame, AnalysisResult>>
  overallState: 'urgent' | 'watch' | 'holding' | 'observe' | 'normal'
}

// ── Nesting map layer ──

export interface NestingLayer {
  timeframe: TimeFrame
  role: 'direction' | 'position' | 'precise' | 'operation'
  analysis: AnalysisResult | null
}

// ── Position tracking ──

export interface Position {
  id: string
  instrument: string
  entrySignal: SignalType
  entryPrice: number
  entryDate: string
  allocation: number
  currentPnl: number
  stopLoss: number
  costZeroProgress: number
  tTrades: number
  status: 'open' | 'closed'
  exitPrice?: number
  exitDate?: string
  exitReason?: string
  signalCorrect?: boolean
  multiLevel?: Partial<Record<TimeFrame, WalkState>>
}

// ── Signal review ──

export interface SignalReview {
  signal: Signal
  outcome: 'correct' | 'incorrect' | 'pending'
  mfe: number
  mae: number
  failureReason?: string
  lesson?: string
}

// ── Chart overlay layer config ──

export type OverlayLayer =
  | 'fractals'
  | 'strokes'
  | 'segments'
  | 'centers'
  | 'signals'
  | 'divergence'
  | 'structure'
  | 'stopLoss'
