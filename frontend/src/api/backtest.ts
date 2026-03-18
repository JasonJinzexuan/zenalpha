import { request } from './request'
import type { BacktestRequest, BacktestResponse } from '@/types'

export function runBacktest(data: BacktestRequest): Promise<BacktestResponse> {
  return request<BacktestResponse>({ method: 'POST', url: '/backtest/run', data })
}
