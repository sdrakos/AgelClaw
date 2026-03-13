import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiJson } from '../lib/api'
import { setAuth } from '../lib/auth'

const ROLE_LABELS = { viewer: 'Αναγνώστης', accountant: 'Λογιστής', owner: 'Διαχειριστής' }

export default function AcceptInvite() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Form fields
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState('')
  const [showPw, setShowPw] = useState(false)

  useEffect(() => {
    apiJson(`/api/invite/${token}`)
      .then((data) => {
        if (data.detail || data.error) {
          setError(data.detail || data.error)
        } else {
          setInfo(data)
        }
      })
      .catch(() => setError('Η πρόσκληση δεν βρέθηκε ή έχει λήξει'))
      .finally(() => setLoading(false))
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError('')
    setSubmitting(true)

    try {
      const body = { password }
      if (!info.has_account) body.name = name

      const data = await apiJson(`/api/invite/${token}/accept`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      if (data.detail || data.error) {
        setFormError(data.detail || data.error)
        return
      }

      // Auto-login
      setAuth(data.token, data.user)
      navigate('/app')
    } catch {
      setFormError('Σφάλμα αποδοχής πρόσκλησης')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600 text-lg font-bold text-white">
              T
            </div>
            <span className="text-2xl font-semibold text-slate-800">Timologia</span>
          </div>
        </div>

        <div className="rounded-xl bg-white p-8 shadow-md">
          {loading && (
            <div className="flex h-32 items-center justify-center text-gray-400">
              Φόρτωση πρόσκλησης...
            </div>
          )}

          {error && (
            <div className="text-center">
              <div className="mb-4 text-4xl">😔</div>
              <h2 className="mb-2 text-lg font-semibold text-slate-800">Μη έγκυρη πρόσκληση</h2>
              <p className="text-sm text-gray-500">{error}</p>
              <button
                onClick={() => navigate('/login')}
                className="mt-6 rounded-md bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
              >
                Σύνδεση
              </button>
            </div>
          )}

          {info && (
            <>
              <div className="mb-6 text-center">
                <h2 className="text-lg font-semibold text-slate-800">Πρόσκληση σε εταιρεία</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Ο/Η <b className="text-slate-700">{info.inviter_name}</b> σας προσκαλεί στην εταιρεία
                </p>
                <p className="mt-1 text-xl font-bold text-indigo-600">{info.company_name}</p>
                <p className="mt-1 text-sm text-gray-400">
                  Ρόλος: <span className="font-medium text-slate-600">{ROLE_LABELS[info.role] || info.role}</span>
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {!info.has_account && (
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">Ονοματεπώνυμο</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      autoFocus
                      placeholder="Εισάγετε το όνομά σας"
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                    />
                  </div>
                )}

                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    {info.has_account ? 'Κωδικός (υπάρχων λογαριασμός)' : 'Κωδικός πρόσβασης'}
                  </label>
                  <div className="relative">
                    <input
                      type={showPw ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      autoFocus={info.has_account}
                      placeholder={info.has_account ? 'Ο κωδικός του λογαριασμού σας' : 'Δημιουργήστε κωδικό'}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 pr-10 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
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
                  {info.has_account && (
                    <p className="mt-1 text-xs text-gray-400">
                      Υπάρχει λογαριασμός με email <b>{info.email}</b>. Εισάγετε τον κωδικό σας.
                    </p>
                  )}
                  {!info.has_account && (
                    <p className="mt-1 text-xs text-gray-400">
                      Θα δημιουργηθεί νέος λογαριασμός με email <b>{info.email}</b>.
                    </p>
                  )}
                </div>

                {formError && (
                  <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{formError}</div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-md bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? 'Αποδοχή...' : info.has_account ? 'Σύνδεση & Αποδοχή' : 'Εγγραφή & Αποδοχή'}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">Powered by <span className="font-semibold text-gray-500">Agel AI</span></p>
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
