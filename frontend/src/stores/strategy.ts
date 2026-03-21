import { create } from 'zustand'

export interface StrategySwitchRecord {
  from: string
  to: string
  timestamp: string
}

interface StrategyState {
  activeStrategy: string
  switchHistory: StrategySwitchRecord[]
  activate: (name: string) => void
  clearHistory: () => void
}

const LS_KEY = 'zen_active_strategy'
const LS_HISTORY_KEY = 'zen_strategy_history'

export const useStrategyStore = create<StrategyState>((set, get) => ({
  activeStrategy: localStorage.getItem(LS_KEY) || 'moderate',
  switchHistory: JSON.parse(localStorage.getItem(LS_HISTORY_KEY) || '[]') as StrategySwitchRecord[],

  activate: (name: string) => {
    const prev = get().activeStrategy
    if (prev === name) return
    const record: StrategySwitchRecord = {
      from: prev,
      to: name,
      timestamp: new Date().toISOString(),
    }
    set((s) => {
      const history = [record, ...s.switchHistory].slice(0, 50)
      localStorage.setItem(LS_KEY, name)
      localStorage.setItem(LS_HISTORY_KEY, JSON.stringify(history))
      return { activeStrategy: name, switchHistory: history }
    })
  },

  clearHistory: () => {
    localStorage.removeItem(LS_HISTORY_KEY)
    set({ switchHistory: [] })
  },
}))
