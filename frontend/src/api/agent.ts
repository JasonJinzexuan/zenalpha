import http from './http'
import type { ScanRequest, ScanResponse, AnalyzeRequest, BacktestRequest, BacktestResponse, NestingBacktestRequest, NestingAnalysisRequest, NestingAnalysisResponse, SyncIngestResponse } from '@/types/api'
import type { AnalysisResult, KLineData, PipelineItem } from '@/types/chan'

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

export async function runNestingBacktest(req: NestingBacktestRequest): Promise<BacktestResponse> {
  const { data } = await http.post<BacktestResponse>(`${AGENT_BASE}/backtest/nesting`, req)
  return data
}

export async function triggerPipeline(
  instruments: string[],
  level: string = '1d',
  limit: number = 300,
): Promise<{ triggered: number; instruments: string[] }> {
  const { data } = await http.post(`${AGENT_BASE}/pipeline/trigger`, {
    instruments,
    level,
    limit,
  })
  return data
}

export async function getPipelineStatus(
  instruments: string[],
  level: string = '1d',
): Promise<PipelineItem[]> {
  const { data } = await http.get<{ items: PipelineItem[] }>(
    `${AGENT_BASE}/pipeline/status`,
    { params: { instruments: instruments.join(','), level } },
  )
  return data.items
}

export async function nestingAnalyze(req: NestingAnalysisRequest): Promise<NestingAnalysisResponse> {
  const { data } = await http.post<NestingAnalysisResponse>(`${AGENT_BASE}/nesting/analyze`, req)
  return data
}

export async function syncIngest(levels: string[] = ['5m', '30m', '1h']): Promise<SyncIngestResponse> {
  const { data } = await http.post<SyncIngestResponse>(`${AGENT_BASE}/ingest/sync`, { levels })
  return data
}
