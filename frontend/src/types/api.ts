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
}
