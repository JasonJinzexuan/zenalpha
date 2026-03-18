import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AnalyzeResponse, ScanResult, TimeFrame } from '@/types'
import { analyzeSignals, scanSignals } from '@/api/signal'
import { getKLines } from '@/api/data'

export const useSignalStore = defineStore('signal', () => {
  const analysisResult = ref<AnalyzeResponse | null>(null)
  const scanResults = ref<ScanResult[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function analyze(instrument: string, timeframe: TimeFrame) {
    loading.value = true
    error.value = null
    try {
      const klines = await getKLines(instrument, timeframe)
      analysisResult.value = await analyzeSignals({ instrument, timeframe, klines })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Analysis failed'
    } finally {
      loading.value = false
    }
  }

  async function scan(instruments: string[], timeframe: TimeFrame) {
    loading.value = true
    error.value = null
    try {
      const response = await scanSignals({ instruments, timeframe })
      scanResults.value = response.results
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Scan failed'
    } finally {
      loading.value = false
    }
  }

  function clearAnalysis() {
    analysisResult.value = null
  }

  return { analysisResult, scanResults, loading, error, analyze, scan, clearAnalysis }
})
