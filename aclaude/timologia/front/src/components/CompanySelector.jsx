import { useState } from 'react'
import { useCompany } from '../context/CompanyContext'
import { apiJson } from '../lib/api'

export default function CompanySelector() {
  const { companies, activeCompanyId, selectCompany, addCompany, loading } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [afm, setAfm] = useState('')
  const [aadeUser, setAadeUser] = useState('')
  const [aadeKey, setAadeKey] = useState('')
  const [aadeEnv, setAadeEnv] = useState('dev')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Φόρτωση...
      </div>
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const data = await apiJson('/api/companies', {
        method: 'POST',
        body: JSON.stringify({
          name, afm,
          aade_user_id: aadeUser,
          aade_subscription_key: aadeKey,
          aade_env: aadeEnv,
        }),
      })
      if (data.error) { setError(data.error); return }
      addCompany(data)
      setShowForm(false)
      setName(''); setAfm(''); setAadeUser(''); setAadeKey(''); setAadeEnv('dev')
    } catch {
      setError('Σφάλμα δημιουργίας')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="flex items-center gap-2">
        {companies.length === 0 ? (
          <span className="text-sm text-gray-400">Καμία εταιρεία</span>
        ) : (
          <select
            value={activeCompanyId || ''}
            onChange={(e) => selectCompany(Number(e.target.value))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.afm})
              </option>
            ))}
          </select>
        )}
        <button
          onClick={() => setShowForm(true)}
          title="Προσθήκη εταιρείας"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-gray-300 text-gray-500 hover:bg-gray-100 hover:text-indigo-600 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowForm(false)}>
          <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-6 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-100">
                <svg className="h-6 w-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-slate-800">Προσθήκη Εταιρείας</h2>
              <p className="mt-1 text-sm text-gray-500">Εισάγετε τα στοιχεία της εταιρείας και τα AADE credentials</p>
            </div>

            {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Επωνυμία *</label>
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} required
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">ΑΦΜ *</label>
                <input type="text" value={afm} onChange={(e) => setAfm(e.target.value)} required maxLength={9}
                  placeholder="123456789"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">AADE User ID</label>
                <input type="text" value={aadeUser} onChange={(e) => setAadeUser(e.target.value)}
                  placeholder="Προαιρετικό — μπορείτε να το προσθέσετε αργότερα"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">AADE Subscription Key</label>
                <input type="password" value={aadeKey} onChange={(e) => setAadeKey(e.target.value)}
                  placeholder="Προαιρετικό"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Περιβάλλον ΑΑΔΕ</label>
                <div className="flex gap-4">
                  {['dev', 'prod'].map((env) => (
                    <label key={env} className="flex items-center gap-2 text-sm text-slate-600">
                      <input type="radio" name="env" value={env} checked={aadeEnv === env}
                        onChange={() => setAadeEnv(env)} className="text-indigo-600" />
                      {env === 'dev' ? 'Δοκιμαστικό' : 'Παραγωγή'}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                  Ακύρωση
                </button>
                <button type="submit" disabled={saving}
                  className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  {saving ? 'Δημιουργία...' : 'Δημιουργία'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
