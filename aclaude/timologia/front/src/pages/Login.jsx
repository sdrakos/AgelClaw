import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiJson } from '../lib/api'
import { setAuth } from '../lib/auth'

export default function Login() {
  const [tab, setTab] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const endpoint = tab === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = tab === 'login'
        ? { email, password }
        : { email, password, name }

      const data = await apiJson(endpoint, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      if (data.error || data.detail) {
        setError(data.error || data.detail)
        return
      }

      setAuth(data.token, data.user)
      navigate('/app')
    } catch {
      setError('Σφάλμα σύνδεσης. Δοκιμάστε ξανά.')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async () => {
    if (!email.trim()) {
      setError('Εισάγετε πρώτα το email σας')
      return
    }
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      const data = await apiJson('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      if (data.error || data.detail) {
        setError(data.error || data.detail)
      } else {
        setSuccess('Σας στάλθηκε email με οδηγίες αλλαγής κωδικού.')
      }
    } catch {
      setError('Σφάλμα αποστολής email')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-500 via-purple-500 to-indigo-700 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/20 backdrop-blur-sm">
            <span className="text-2xl font-bold text-white">T</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Timologia</h1>
          <p className="mt-1 text-indigo-200">Διαχείριση Παραστατικών</p>
        </div>

        <div className="rounded-2xl bg-white p-8 shadow-xl">
          {/* Tabs */}
          <div className="mb-6 flex rounded-lg bg-gray-100 p-1">
            <button
              onClick={() => { setTab('login'); setError(''); setSuccess('') }}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                tab === 'login'
                  ? 'bg-white text-slate-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Σύνδεση
            </button>
            <button
              onClick={() => { setTab('register'); setError(''); setSuccess('') }}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                tab === 'register'
                  ? 'bg-white text-slate-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Εγγραφή
            </button>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
          )}
          {success && (
            <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-600">{success}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {tab === 'register' && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Όνομα</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Το όνομά σας"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-colors"
                  required
                />
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-colors"
                required
              />
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Κωδικός</label>
                {tab === 'login' && (
                  <button
                    type="button"
                    onClick={handleForgotPassword}
                    className="text-xs font-medium text-indigo-600 hover:text-indigo-500 transition-colors"
                  >
                    Ξέχασα τον κωδικό
                  </button>
                )}
              </div>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 pr-10 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-colors"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-gray-400 hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Παρακαλώ περιμένετε...' : tab === 'login' ? 'Σύνδεση' : 'Εγγραφή'}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-indigo-300/70">Powered by <span className="font-semibold text-indigo-200/80">Agel AI</span></p>
      </div>
    </div>
  )
}

function EyeIcon() {
  return (
    <svg className="h-4.5 w-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg className="h-4.5 w-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  )
}
