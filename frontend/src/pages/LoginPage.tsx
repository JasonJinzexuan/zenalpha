import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

export default function LoginPage() {
  const nav = useNavigate()
  const authLogin = useAuthStore((s) => s.login)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      if (mode === 'register') {
        await register({ username, email, password })
        setMode('login')
        setError('')
      } else {
        const res = await login({ username, password })
        authLogin(res.token, res.username, res.role)
        nav('/overview', { replace: true })
      }
    } catch (err: any) {
      setError(err.message || 'Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="text-accent-cyan text-2xl font-bold tracking-[6px]">ZEN<span className="text-text-muted">ALPHA</span></div>
          <div className="text-text-muted text-[10px] tracking-[4px] mt-2">CHAN THEORY TERMINAL</div>
        </div>

        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          <div className="text-xs text-accent-cyan tracking-wider mb-4">
            {mode === 'login' ? 'SYSTEM ACCESS' : 'NEW OPERATOR'}
          </div>

          <input
            className="input w-full"
            placeholder="USERNAME"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
          {mode === 'register' && (
            <input
              className="input w-full"
              type="email"
              placeholder="EMAIL"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          )}
          <input
            className="input w-full"
            type="password"
            placeholder="PASSWORD"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          {error && (
            <div className="text-accent-red text-[11px] bg-accent-red/5 border border-accent-red/20 rounded px-3 py-2">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
            {loading ? 'PROCESSING...' : mode === 'login' ? 'LOGIN' : 'REGISTER'}
          </button>

          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            className="text-text-dim text-[10px] tracking-wider hover:text-accent-cyan transition-colors w-full text-center cursor-pointer bg-transparent border-0"
          >
            {mode === 'login' ? 'CREATE NEW ACCOUNT' : 'BACK TO LOGIN'}
          </button>
        </form>
      </div>
    </div>
  )
}
