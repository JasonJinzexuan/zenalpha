import { request } from './request'
import type { RawKLine, Instrument, TimeFrame } from '@/types'

export function getKLines(
  instrument: string,
  timeframe: TimeFrame = '1d',
  limit: number = 500
): Promise<RawKLine[]> {
  return request<RawKLine[]>({
    method: 'GET',
    url: `/data/klines/${instrument}`,
    params: { timeframe, limit },
  })
}

export function syncKLines(instrument: string, timeframe: TimeFrame = '1d'): Promise<void> {
  return request<void>({ method: 'POST', url: '/data/klines/sync', data: { instrument, timeframe } })
}

export function getInstruments(): Promise<Instrument[]> {
  return request<Instrument[]>({ method: 'GET', url: '/data/instruments' })
}
