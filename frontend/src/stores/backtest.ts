import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BacktestResponse } from '@/types'
import { runBacktest } from '@/api/backtest'

export const useBacktestStore = defineStore('backtest', () => {
  const result = ref<BacktestResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function run(instrument: string, startDate: string, endDate: string, initialCash: number) {
    loading.value = true
    error.value = null
    try {
      result.value = await runBacktest({ instrument, startDate, endDate, initialCash })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Backtest failed'
    } finally {
      loading.value = false
    }
  }

  function clear() {
    result.value = null
  }

  return { result, loading, error, run, clear }
})
