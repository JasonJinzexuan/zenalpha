export type Direction = 'UP' | 'DOWN'
export type FractalType = 'TOP' | 'BOTTOM'
export type TimeFrame = '1m' | '5m' | '30m' | '1h' | '1d' | '1w' | '1M'
export type SignalType = 'B1' | 'B2' | 'B3' | 'S1' | 'S2' | 'S3'
export type TrendClass = 'UP_TREND' | 'DOWN_TREND' | 'CONSOLIDATION'
export type DivergenceType = 'TREND' | 'CONSOLIDATION'

export interface RawKLine {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  timeframe: TimeFrame
}

export interface StandardKLine {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  originalCount: number
  direction: Direction
}

export interface Fractal {
  type: FractalType
  timestamp: string
  extremeValue: number
  klineIndex: number
}

export interface MACDValue {
  dif: number
  dea: number
  histogram: number
}

export interface Stroke {
  direction: Direction
  high: number
  low: number
  klineCount: number
  macdArea: number
  startTime: string
  endTime: string
}

export interface Segment {
  direction: Direction
  high: number
  low: number
  strokes: Stroke[]
  terminationType: 'FIRST_KIND' | 'SECOND_KIND'
}

export interface Center {
  level: TimeFrame
  zg: number
  zd: number
  gg: number
  dd: number
  startTime: string
  endTime: string
  extensionCount: number
}

export interface Signal {
  signalType: SignalType
  level: TimeFrame
  instrument: string
  timestamp: string
  price: number
  strength: number
  sourceLesson: string
  reasoning: string
}

export interface IntervalNesting {
  targetLevel: TimeFrame
  nestingDepth: number
  directionAligned: boolean
  confidence: number
}

export interface ScanResult {
  instrument: string
  signal: Signal
  nesting: IntervalNesting | null
  score: number
  rank: number
  scanTime: string
}

export interface AnalyzeRequest {
  instrument: string
  timeframe: TimeFrame
  klines: RawKLine[]
}

export interface AnalyzeResponse {
  klines: StandardKLine[]
  fractals: Fractal[]
  strokes: Stroke[]
  segments: Segment[]
  centers: Center[]
  signals: Signal[]
  macdValues: MACDValue[]
}

export interface ScanRequest {
  instruments: string[]
  timeframe: TimeFrame
}

export interface ScanResponse {
  results: ScanResult[]
}

export interface BacktestRequest {
  instrument: string
  startDate: string
  endDate: string
  initialCash: number
}

export interface BacktestMetrics {
  totalReturn: number
  annualizedReturn: number
  sharpeRatio: number
  sortinoRatio: number
  calmarRatio: number
  maxDrawdown: number
  winRate: number
  profitFactor: number
  totalTrades: number
  avgTradePnl: number
}

export interface Trade {
  instrument: string
  direction: Direction
  entryPrice: number
  exitPrice: number
  entryTime: string
  exitTime: string
  quantity: number
  pnl: number
  pnlPct: number
  signalType: SignalType
  exitReason: string
}

export interface PortfolioSnapshot {
  timestamp: string
  cash: number
  equity: number
  drawdown: number
  peakEquity: number
}

export interface BacktestResponse {
  metrics: BacktestMetrics
  snapshots: PortfolioSnapshot[]
  trades: Trade[]
}

export interface ApiResponse<T> {
  success: boolean
  data: T | null
  error: string | null
}

export interface Instrument {
  id: number
  symbol: string
  name: string
  sector: string
  marketCap: number
  active: boolean
}
