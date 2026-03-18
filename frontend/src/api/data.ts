import http from './http'
import type { KLineData } from '@/types/chan'

const AGENT_BASE = '/agents'

export async function getKLines(
  instrument: string,
  timeframe: string = '1d',
  limit: number = 500,
): Promise<KLineData[]> {
  const { data } = await http.get<{ instrument: string; level: string; klines: KLineData[] }>(
    `${AGENT_BASE}/klines/${instrument}`,
    { params: { level: timeframe, limit } },
  )
  return data.klines
}

export async function ingestKLines(
  instrument: string,
  level: string = '1d',
  limit: number = 500,
): Promise<{ instrument: string; records_written: number }> {
  const { data } = await http.post<{ instrument: string; level: string; records_written: number; source: string }>(
    `${AGENT_BASE}/ingest`,
    { instrument, level, limit },
  )
  return data
}
