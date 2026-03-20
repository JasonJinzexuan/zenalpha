export interface ApiResponse<T> {
  success: boolean
  data: T
  error: string | null
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface LoginResponse {
  token: string
  username: string
  role: string
}

export interface ScanRequest {
  instruments: string[]
  level: string
  limit: number
}

export interface ScanResponse {
  results: import('./chan').ScanResultItem[]
  source: string
}

export interface AnalyzeRequest {
  instrument: string
  level: string
  klines: {
    timestamp: string
    open: string
    high: string
    low: string
    close: string
    volume: number
  }[]
}

export interface BacktestRequest {
  instruments: Record<string, {
    timestamp: string
    open: string
    high: string
    low: string
    close: string
    volume: number
  }[]>
  initial_cash: string
  level?: string
}

export interface NestingBacktestRequest {
  instruments: string[]
  initial_cash: string
  levels?: string[]
  exec_level?: string
  limit?: number
  min_nesting_depth?: number
  require_alignment?: boolean
}

export interface TradeLogEntry {
  action: string
  instrument: string
  timestamp: string
  price: string
  signal: string
  nesting_depth: number
  aligned: boolean
  large: string | null
  medium: string | null
  precise: string | null
}

export interface BacktestResponse {
  total_return: string
  annualized_return: string
  sharpe_ratio: string
  sortino_ratio: string
  max_drawdown: string
  win_rate: string
  profit_factor: string
  total_trades: number
  trade_log: TradeLogEntry[]
}

export interface NestingAnalysisRequest {
  instrument: string
  use_llm: boolean
}

export interface ToolCallLog {
  iteration: number
  tool: string
  args: Record<string, unknown>
  result_summary: Record<string, unknown>
}

export interface NestingAnalysisResponse {
  instrument: string
  nesting_path: string[]
  target_level: string
  large_signal: string | null
  medium_signal: string | null
  precise_signal: string | null
  nesting_depth: number
  direction_aligned: boolean
  confidence: string
  confidence_source: string
  reasoning: string
  risk_assessment: string
  tool_calls: ToolCallLog[]
  iterations: number
}

export interface SyncIngestResponse {
  total_written: number
  details: { instrument: string; level: string; records_written: number; status?: string; last_before?: string; error?: string }[]
}
