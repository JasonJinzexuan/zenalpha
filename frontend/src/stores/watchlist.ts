import { create } from 'zustand'

const DEFAULT_WATCHLIST = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
  'JPM', 'V', 'UNH',
]

interface WatchlistState {
  instruments: string[]
  add: (symbol: string) => void
  remove: (symbol: string) => void
  reset: () => void
}

export const useWatchlistStore = create<WatchlistState>((set) => ({
  instruments: JSON.parse(localStorage.getItem('zen_watchlist') || 'null') || DEFAULT_WATCHLIST,

  add: (symbol) =>
    set((s) => {
      const next = [...new Set([...s.instruments, symbol.toUpperCase()])]
      localStorage.setItem('zen_watchlist', JSON.stringify(next))
      return { instruments: next }
    }),

  remove: (symbol) =>
    set((s) => {
      const next = s.instruments.filter((i) => i !== symbol)
      localStorage.setItem('zen_watchlist', JSON.stringify(next))
      return { instruments: next }
    }),

  reset: () => {
    localStorage.removeItem('zen_watchlist')
    set({ instruments: DEFAULT_WATCHLIST })
  },
}))
