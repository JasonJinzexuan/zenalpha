import { request } from './request'
import type { AnalyzeRequest, AnalyzeResponse, ScanRequest, ScanResponse } from '@/types'

export function analyzeSignals(data: AnalyzeRequest): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>({ method: 'POST', url: '/signals/analyze', data })
}

export function scanSignals(data: ScanRequest): Promise<ScanResponse> {
  return request<ScanResponse>({ method: 'POST', url: '/signals/scan', data })
}
