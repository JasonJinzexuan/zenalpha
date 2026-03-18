import { create } from 'zustand'

interface AuthState {
  token: string | null
  username: string | null
  role: string | null
  isLoggedIn: boolean
  login: (token: string, username: string, role: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('zen_token'),
  username: (() => {
    try { return JSON.parse(localStorage.getItem('zen_user') || '{}').username || null } catch { return null }
  })(),
  role: (() => {
    try { return JSON.parse(localStorage.getItem('zen_user') || '{}').role || null } catch { return null }
  })(),
  get isLoggedIn() { return !!this.token },

  login: (token, username, role) => {
    localStorage.setItem('zen_token', token)
    localStorage.setItem('zen_user', JSON.stringify({ username, role }))
    set({ token, username, role })
  },

  logout: () => {
    localStorage.removeItem('zen_token')
    localStorage.removeItem('zen_user')
    set({ token: null, username: null, role: null })
  },
}))
