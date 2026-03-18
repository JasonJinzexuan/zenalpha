import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('za_token'))
  const username = ref<string | null>(localStorage.getItem('za_username'))
  const role = ref<string | null>(localStorage.getItem('za_role'))

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(t: string, u: string, r: string) {
    token.value = t
    username.value = u
    role.value = r
    localStorage.setItem('za_token', t)
    localStorage.setItem('za_username', u)
    localStorage.setItem('za_role', r)
  }

  function logout() {
    token.value = null
    username.value = null
    role.value = null
    localStorage.removeItem('za_token')
    localStorage.removeItem('za_username')
    localStorage.removeItem('za_role')
  }

  return { token, username, role, isAuthenticated, setAuth, logout }
})
