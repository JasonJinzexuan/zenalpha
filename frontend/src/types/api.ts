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

export interface PerLevelInfo {
  trend: string | null
  direction: string | null  // "多" | "空" | null
  signal: string | null
  has_structure: boolean
}

export interface NestingAnalysisResponse {
  instrument: string
  nesting_path: string[]
  per_level?: Record<string, PerLevelInfo>
  target_level: string
  large_signal: string | null
  medium_signal: string | null
  precise_signal: string | null
  nesting_depth: number
  direction_aligned: boolean
  confidence: string
  actionable?: boolean
  status?: string
  confidence_source: string
  reasoning: string
  risk_assessment: string
  tool_calls: ToolCallLog[]
  iterations: number
}

export interface DecisionRecord {
  instrument: string
  timestamp: string
  action: 'BUY' | 'SELL'
  price_current: string
  price_range_low: string
  price_range_high: string
  stop_loss: string
  position_size: string
  urgency: string
  confidence: number
  signal_basis: string
  macro_context: string
  reasoning: string
  nesting_summary: Record<string, unknown>
}

export interface DecisionTriggerResponse {
  triggered: number
  decisions: DecisionRecord[]
}

export interface DecisionHistoryResponse {
  decisions: DecisionRecord[]
}

export interface DecisionLatestResponse {
  decisions: DecisionRecord[]
}

export interface SyncIngestResponse {
  total_written: number
  details: { instrument: string; level: string; records_written: number; status?: string; last_before?: string; error?: string }[]
}

// ── Strategy Lab types ──────────────────────────────────────────────────────

export interface StrategyParams {
  min_nesting_depth: number
  min_confidence: string
  require_alignment: boolean
  divergence_ratio_max: string
  min_signal_strength: string
  allowed_signals: string[]
  signal_expiry_bars: number
  exit_on_reverse_signal: boolean
}

export interface RiskParams {
  stop_loss_atr_mult: string
  take_profit_atr_mult: string
  trailing_stop_enabled: boolean
  trailing_stop_pct: string
  max_position_pct: string
  use_atr_sizing: boolean
  max_daily_loss_pct: string
  max_weekly_loss_pct: string
  max_drawdown_pct: string
  max_concurrent_positions: number
  regime_filter: string[]
}

export interface StrategyTemplate {
  name: string
  description: string
  strategy: StrategyParams
  risk: RiskParams
  qualification_thresholds?: {
    min_win_rate: string
    min_profit_factor: string
    max_allowed_drawdown: string
    min_sharpe: string
  }
  qualified?: boolean
}

export interface StrategyBacktestRequest {
  strategy_name?: string
  strategy?: StrategyParams
  risk?: RiskParams
  instruments?: string[]
  initial_cash?: string
  start_date?: string
  end_date?: string
}

export interface QualificationGate {
  value: string
  threshold: string
  pass: boolean
}

export interface SignalStat {
  signal_type: string
  trades: number
  wins: number
  win_rate: string
  total_pnl: string
}

export interface StrategyBacktestResponse {
  strategy: string
  qualified: boolean
  metrics: {
    total_return: string
    annualized_return: string
    sharpe_ratio: string
    sortino_ratio: string
    calmar_ratio: string
    max_drawdown: string
    win_rate: string
    profit_factor: string
    total_trades: number
    avg_trade_pnl: string
  }
  qualification: Record<string, QualificationGate>
  signal_stats: SignalStat[]
  trade_count: number
  equity_curve: { timestamp: string; equity: string }[]
  strategy_params: StrategyParams
  risk_params: RiskParams
}

export interface SensitivityRequest {
  param_name: string
  values: string[]
  base_strategy?: StrategyParams
  base_risk?: RiskParams
  instruments?: string[]
}

export interface SensitivityResult {
  param_value: string
  win_rate: string
  profit_factor: string
  max_drawdown: string
  sharpe_ratio: string
  total_trades: number
  total_return: string
}

export interface SensitivityResponse {
  param_name: string
  results: SensitivityResult[]
}
