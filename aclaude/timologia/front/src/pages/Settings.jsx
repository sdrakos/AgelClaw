import { useState, useEffect } from 'react'
import { apiJson, api } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import { getUser } from '../lib/auth'

const TABS = [
  { key: 'company', label: 'Εταιρεία' },
  { key: 'members', label: 'Μέλη' },
  { key: 'account', label: 'Λογαριασμός' },
]

const ROLES = [
  { value: 'admin', label: 'Διαχειριστής' },
  { value: 'accountant', label: 'Λογιστής' },
  { value: 'viewer', label: 'Αναγνώστης' },
]

export default function Settings() {
  const { activeCompanyId } = useCompany()
  const [tab, setTab] = useState('company')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const user = getUser()

  // Company state
  const [companyName, setCompanyName] = useState('')
  const [companyAfm, setCompanyAfm] = useState('')
  const [aadeUser, setAadeUser] = useState('')
  const [aadeKey, setAadeKey] = useState('')
  const [aadeEnv, setAadeEnv] = useState('dev')

  // Members state
  const [members, setMembers] = useState([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('viewer')

  useEffect(() => {
    if (!activeCompanyId) return
    setLoading(true)
    setError('')

    apiJson(`/api/companies/${activeCompanyId}`)
      .then((data) => {
        const c = data.company || data
        setCompanyName(c.name || '')
        setCompanyAfm(c.afm || '')
        setAadeUser(c.aade_user_id ? '********' : '')
        setAadeKey(c.aade_subscription_key ? '********' : '')
        setAadeEnv(c.aade_env || 'dev')
      })
      .catch(() => {})
      .finally(() => setLoading(false))

    apiJson(`/api/companies/${activeCompanyId}/members`)
      .then((data) => setMembers(data.members || data || []))
      .catch(() => setMembers([]))
  }, [activeCompanyId])

  const saveCompany = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const body = {
        name: companyName,
        afm: companyAfm,
        aade_env: aadeEnv,
      }
      // Only send credentials if changed from masked value
      if (aadeUser && aadeUser !== '********') body.aade_user_id = aadeUser
      if (aadeKey && aadeKey !== '********') body.aade_subscription_key = aadeKey

      const data = await apiJson(`/api/companies/${activeCompanyId}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      })
      if (data.error) setError(data.error)
      else setSuccess('Αποθηκεύτηκε!')
    } catch {
      setError('Σφάλμα αποθήκευσης')
    } finally {
      setSaving(false)
    }
  }

  const inviteMember = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    try {
      const data = await apiJson(`/api/companies/${activeCompanyId}/members`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      })
      if (data.error) {
        setError(data.error)
        return
      }
      setMembers((prev) => [...prev, data.member || data])
      setInviteEmail('')
      setSuccess('Η πρόσκληση στάλθηκε!')
    } catch {
      setError('Σφάλμα πρόσκλησης')
    }
  }

  const updateMemberRole = async (memberId, role) => {
    try {
      await apiJson(`/api/companies/${activeCompanyId}/members/${memberId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      })
      setMembers((prev) =>
        prev.map((m) => (m.id === memberId ? { ...m, role } : m))
      )
    } catch {}
  }

  const removeMember = async (memberId) => {
    try {
      await api(`/api/companies/${activeCompanyId}/members/${memberId}`, { method: 'DELETE' })
      setMembers((prev) => prev.filter((m) => m.id !== memberId))
    } catch {}
  }

  if (!activeCompanyId) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-800">Ρυθμίσεις</h1>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setError(''); setSuccess('') }}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-white text-slate-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}
      {success && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-600">{success}</div>}

      {/* Company tab */}
      {tab === 'company' && (
        <form onSubmit={saveCompany} className="rounded-lg bg-white p-6 shadow-sm space-y-4 max-w-xl">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-gray-400">Φόρτωση...</div>
          ) : (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Επωνυμία</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">ΑΦΜ</label>
                <input
                  type="text"
                  value={companyAfm}
                  onChange={(e) => setCompanyAfm(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  maxLength={9}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">AADE User ID</label>
                <input
                  type="text"
                  value={aadeUser}
                  onChange={(e) => setAadeUser(e.target.value)}
                  onFocus={(e) => { if (e.target.value === '********') setAadeUser('') }}
                  placeholder="Εισάγετε AADE User ID"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">AADE Subscription Key</label>
                <input
                  type="password"
                  value={aadeKey}
                  onChange={(e) => setAadeKey(e.target.value)}
                  onFocus={(e) => { if (e.target.value === '********') setAadeKey('') }}
                  placeholder="Εισάγετε AADE Subscription Key"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Περιβάλλον ΑΑΔΕ</label>
                <div className="flex gap-3">
                  {['dev', 'prod'].map((env) => (
                    <label key={env} className="flex items-center gap-2 text-sm text-slate-600">
                      <input
                        type="radio"
                        name="aade_env"
                        value={env}
                        checked={aadeEnv === env}
                        onChange={() => setAadeEnv(env)}
                        className="text-indigo-600 focus:ring-indigo-500"
                      />
                      {env === 'dev' ? 'Δοκιμαστικό' : 'Παραγωγή'}
                    </label>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {saving ? 'Αποθήκευση...' : 'Αποθήκευση'}
              </button>
            </>
          )}
        </form>
      )}

      {/* Members tab */}
      {tab === 'members' && (
        <div className="space-y-4 max-w-2xl">
          {/* Invite form */}
          <form onSubmit={inviteMember} className="rounded-lg bg-white p-5 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-700">Πρόσκληση Μέλους</h3>
            <div className="flex flex-wrap gap-3">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="Email μέλους"
                required
                className="flex-1 min-w-[200px] rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <button
                type="submit"
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
              >
                Πρόσκληση
              </button>
            </div>
          </form>

          {/* Members table */}
          <div className="rounded-lg bg-white shadow-sm">
            {members.length === 0 ? (
              <div className="flex h-24 items-center justify-center text-gray-400">
                Δεν βρέθηκαν μέλη
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-100 text-left text-xs font-medium uppercase text-gray-500">
                      <th className="px-4 py-3">Όνομα</th>
                      <th className="px-4 py-3">Email</th>
                      <th className="px-4 py-3">Ρόλος</th>
                      <th className="px-4 py-3">Ενέργειες</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.id || m.user_id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-slate-700">{m.name || '-'}</td>
                        <td className="px-4 py-3 text-slate-600">{m.email}</td>
                        <td className="px-4 py-3">
                          <select
                            value={m.role}
                            onChange={(e) => updateMemberRole(m.id || m.user_id, e.target.value)}
                            className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-indigo-500 outline-none"
                          >
                            {ROLES.map((r) => (
                              <option key={r.value} value={r.value}>{r.label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => removeMember(m.id || m.user_id)}
                            className="text-red-500 hover:text-red-700 text-xs font-medium"
                          >
                            Αφαίρεση
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Account tab */}
      {tab === 'account' && (
        <div className="rounded-lg bg-white p-6 shadow-sm max-w-xl space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-500">Όνομα</label>
            <p className="text-slate-700">{user?.name || '-'}</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-500">Email</label>
            <p className="text-slate-700">{user?.email || '-'}</p>
          </div>
        </div>
      )}
    </div>
  )
}
