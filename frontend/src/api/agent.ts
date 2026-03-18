import http from './http'
import type { ScanRequest, ScanResponse, AnalyzeRequest, BacktestRequest, BacktestResponse } from '@/types/api'
import type { AnalysisResult, KLineData } from '@/types/chan'

const AGENT_BASE = '/agents'

export async function healthCheck(): Promise<{ status: string; timestream: string }> {
  const { data } = await http.get(`${AGENT_BASE}/health`)
  return data
}

export async function scanInstruments(req: ScanRequest): Promise<ScanResponse> {
  const { data } = await http.post<ScanResponse>(`${AGENT_BASE}/scan`, req)
  return data
}

export async function analyzeInstrument(
  instrument: string,
  level: string,
  klines: KLineData[],
): Promise<AnalysisResult> {
  const payload: AnalyzeRequest = {
    instrument,
    level,
    klines: klines.map((k) => ({
      timestamp: k.timestamp,
      open: String(k.open),
      high: String(k.high),
      low: String(k.low),
      close: String(k.close),
      volume: k.volume,
    })),
  }
  const { data } = await http.post<AnalysisResult>(`${AGENT_BASE}/analyze`, payload)
  return data
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  const { data } = await http.post<BacktestResponse>(`${AGENT_BASE}/backtest`, req)
  return data
}
