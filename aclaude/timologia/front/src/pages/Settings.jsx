import { useState, useEffect } from 'react'
import { apiJson, api } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import { getUser } from '../lib/auth'

const TABS = [
  { key: 'company', label: 'Εταιρεία', icon: CompanyIcon },
  { key: 'members', label: 'Μέλη', icon: MembersIcon },
  { key: 'account', label: 'Λογαριασμός', icon: AccountIcon },
]

const ROLES = [
  { value: 'owner', label: 'Ιδιοκτήτης' },
  { value: 'accountant', label: 'Λογιστής' },
  { value: 'viewer', label: 'Αναγνώστης' },
]

const ROLE_BADGES = {
  owner: 'bg-indigo-100 text-indigo-700',
  accountant: 'bg-emerald-100 text-emerald-700',
  viewer: 'bg-slate-100 text-slate-600',
  admin: 'bg-purple-100 text-purple-700',
}

export default function Settings() {
  const { activeCompanyId, companies } = useCompany()
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
  const [invitations, setInvitations] = useState([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('viewer')
  const [inviting, setInviting] = useState(false)

  useEffect(() => {
    if (!activeCompanyId) return
    setLoading(true)
    setError('')

    const company = companies.find((c) => c.id === activeCompanyId)
    if (company) {
      setCompanyName(company.name || '')
      setCompanyAfm(company.afm || '')
      setAadeEnv(company.aade_env || 'dev')
      setAadeUser('********')
      setAadeKey('********')
    }
    setLoading(false)

    apiJson(`/api/companies/${activeCompanyId}/members`)
      .then((data) => setMembers(data.members || data || []))
      .catch(() => setMembers([]))

    apiJson(`/api/companies/${activeCompanyId}/invitations`)
      .then((data) => setInvitations(Array.isArray(data) ? data : []))
      .catch(() => setInvitations([]))
  }, [activeCompanyId, companies])

  const saveCompany = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const body = { name: companyName, afm: companyAfm, aade_env: aadeEnv }
      if (aadeUser && aadeUser !== '********') body.aade_user_id = aadeUser
      if (aadeKey && aadeKey !== '********') body.aade_subscription_key = aadeKey

      const data = await apiJson(`/api/companies/${activeCompanyId}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      })
      if (data.error || data.detail) setError(data.error || data.detail)
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
    setInviting(true)

    try {
      const data = await apiJson(`/api/companies/${activeCompanyId}/members`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      })
      if (data.error || data.detail) {
        setError(data.error || data.detail)
        return
      }
      setInviteEmail('')
      setSuccess(data.message || 'Η πρόσκληση στάλθηκε!')
      apiJson(`/api/companies/${activeCompanyId}/invitations`)
        .then((d) => setInvitations(Array.isArray(d) ? d : []))
        .catch(() => {})
    } catch {
      setError('Σφάλμα πρόσκλησης')
    } finally {
      setInviting(false)
    }
  }

  const cancelInvitation = async (id) => {
    try {
      await api(`/api/invitations/${id}`, { method: 'DELETE' })
      setInvitations((prev) => prev.filter((i) => i.id !== id))
    } catch {}
  }

  const removeMember = async (memberId) => {
    if (!confirm('Αφαίρεση μέλους;')) return
    try {
      await api(`/api/companies/${activeCompanyId}/members/${memberId}`, { method: 'DELETE' })
      setMembers((prev) => prev.filter((m) => (m.user_id || m.id) !== memberId))
    } catch {}
  }

  if (!activeCompanyId) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  const pendingInvitations = invitations.filter((i) => i.status === 'pending')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Ρυθμίσεις</h1>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-full sm:w-fit overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setError(''); setSuccess('') }}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-white text-slate-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <t.icon />
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-600">
          <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          {success}
        </div>
      )}

      {/* ═══ Company tab ═══ */}
      {tab === 'company' && (
        <form onSubmit={saveCompany} className="rounded-xl bg-white p-4 sm:p-6 shadow-sm space-y-5 max-w-xl">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-gray-400">Φόρτωση...</div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-sm font-medium text-slate-700">Επωνυμία</label>
                  <input type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors" />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">ΑΦΜ</label>
                  <input type="text" value={companyAfm} onChange={(e) => setCompanyAfm(e.target.value)} maxLength={9}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-slate-700 font-mono focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors" />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Περιβάλλον ΑΑΔΕ</label>
                  <div className="flex gap-4 pt-2">
                    {[{ v: 'dev', l: 'Δοκιμαστικό' }, { v: 'prod', l: 'Παραγωγή' }].map(({ v, l }) => (
                      <label key={v} className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                        <input type="radio" name="aade_env" value={v} checked={aadeEnv === v}
                          onChange={() => setAadeEnv(v)} className="text-indigo-600 focus:ring-indigo-500" />
                        {l}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-400">Διαπιστευτήρια ΑΑΔΕ</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">User ID</label>
                    <input type="text" value={aadeUser} onChange={(e) => setAadeUser(e.target.value)}
                      onFocus={(e) => { if (e.target.value === '********') setAadeUser('') }}
                      placeholder="AADE User ID"
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">Subscription Key</label>
                    <input type="password" value={aadeKey} onChange={(e) => setAadeKey(e.target.value)}
                      onFocus={(e) => { if (e.target.value === '********') setAadeKey('') }}
                      placeholder="AADE Subscription Key"
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors" />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button type="submit" disabled={saving}
                  className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  {saving ? 'Αποθήκευση...' : 'Αποθήκευση'}
                </button>
              </div>
            </>
          )}
        </form>
      )}

      {/* ═══ Members tab ═══ */}
      {tab === 'members' && (
        <div className="space-y-5">

          {/* Invite form */}
          <div className="rounded-xl bg-white p-5 shadow-sm">
            <h3 className="mb-1 text-sm font-semibold text-slate-800">Πρόσκληση Νέου Μέλους</h3>
            <p className="mb-4 text-xs text-slate-400">Θα σταλεί email πρόσκληση. Αν δεν έχει λογαριασμό, θα δημιουργήσει κατά την αποδοχή.</p>
            <form onSubmit={inviteMember} className="flex flex-col sm:flex-row sm:flex-wrap sm:items-end gap-3">
              <div className="flex-1 min-w-[220px]">
                <label className="mb-1 block text-xs font-medium text-slate-500">Email</label>
                <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com" required
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">Ρόλος</label>
                <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                  className="rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors">
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={inviting}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                {inviting ? (
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                )}
                Πρόσκληση
              </button>
            </form>
          </div>

          {/* Active members */}
          <div className="rounded-xl bg-white shadow-sm">
            <div className="border-b border-gray-100 px-5 py-3">
              <h3 className="text-sm font-semibold text-slate-800">Ενεργά Μέλη ({members.length})</h3>
            </div>
            {members.length === 0 ? (
              <div className="flex h-20 items-center justify-center text-sm text-gray-400">Δεν βρέθηκαν μέλη</div>
            ) : (
              <div className="divide-y divide-gray-50">
                {members.map((m) => (
                  <div key={m.user_id || m.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-600">
                        {(m.name || m.email || '?')[0].toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-700">{m.name || '-'}</p>
                        <p className="text-xs text-slate-400">{m.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_BADGES[m.role] || ROLE_BADGES.viewer}`}>
                        {ROLES.find((r) => r.value === m.role)?.label || m.role}
                      </span>
                      {m.role !== 'owner' && (
                        <button onClick={() => removeMember(m.user_id || m.id)}
                          className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                          title="Αφαίρεση">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pending invitations */}
          {pendingInvitations.length > 0 && (
            <div className="rounded-xl bg-white shadow-sm">
              <div className="border-b border-amber-100 bg-amber-50/50 px-5 py-3 rounded-t-xl">
                <h3 className="text-sm font-semibold text-amber-800">Εκκρεμείς Προσκλήσεις ({pendingInvitations.length})</h3>
              </div>
              <div className="divide-y divide-gray-50">
                {pendingInvitations.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-sm text-amber-600">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-700">{inv.email}</p>
                        <p className="text-xs text-slate-400">
                          {inv.created_at ? new Date(inv.created_at).toLocaleDateString('el-GR') : ''} — λήγει {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString('el-GR') : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_BADGES[inv.role] || ROLE_BADGES.viewer}`}>
                        {ROLES.find((r) => r.value === inv.role)?.label || inv.role}
                      </span>
                      <button onClick={() => cancelInvitation(inv.id)}
                        className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                        title="Ακύρωση">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ Account tab ═══ */}
      {tab === 'account' && (
        <div className="rounded-xl bg-white p-6 shadow-sm max-w-xl">
          <div className="flex items-center gap-4 mb-6">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100 text-xl font-bold text-indigo-600">
              {(user?.name || user?.email || '?')[0].toUpperCase()}
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-800">{user?.name || '-'}</p>
              <p className="text-sm text-slate-400">{user?.email || '-'}</p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 border-t border-gray-100 pt-4">
            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-slate-400">Ρόλος Πλατφόρμας</label>
              <p className="mt-1 text-sm text-slate-700 capitalize">{user?.role || 'user'}</p>
            </div>
            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-slate-400">Εταιρείες</label>
              <p className="mt-1 text-sm text-slate-700">{companies.length}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function CompanyIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
    </svg>
  )
}

function MembersIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  )
}

function AccountIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  )
}
