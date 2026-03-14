import { useState, useEffect } from 'react'
import { apiJson } from '../lib/api'

export default function Admin() {
  const [users, setUsers] = useState([])
  const [companies, setCompanies] = useState([])
  const [overview, setOverview] = useState({})
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('users')

  useEffect(() => {
    Promise.all([
      apiJson('/api/admin/users'),
      apiJson('/api/admin/companies'),
      apiJson('/api/admin/overview'),
    ])
      .then(([u, c, o]) => {
        setUsers(u)
        setCompanies(c)
        setOverview(o)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const changeRole = async (userId, newRole) => {
    if (!confirm(`Αλλαγή ρόλου σε "${newRole}";`)) return
    await apiJson(`/api/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role: newRole }),
    })
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
    )
  }

  const deleteUser = async (userId, email) => {
    if (!confirm(`Διαγραφή χρήστη ${email}; Αυτή η ενέργεια δεν αναιρείται.`)) return
    await apiJson(`/api/admin/users/${userId}`, { method: 'DELETE' })
    setUsers((prev) => prev.filter((u) => u.id !== userId))
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Φόρτωση...
      </div>
    )
  }

  const TABS = [
    { key: 'users', label: 'Χρήστες' },
    { key: 'companies', label: 'Εταιρείες' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Διαχείριση</h1>

      {/* Overview cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Χρήστες', value: overview.users, color: 'bg-indigo-500' },
          { label: 'Εταιρείες', value: overview.companies, color: 'bg-emerald-500' },
          { label: 'Παραστατικά', value: overview.invoices, color: 'bg-amber-500' },
        ].map((card) => (
          <div key={card.label} className="rounded-lg bg-white p-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className={`h-10 w-10 rounded-lg ${card.color} flex items-center justify-center`}>
                <div className="h-5 w-5 rounded-full bg-white/30" />
              </div>
              <div>
                <p className="text-sm text-gray-500">{card.label}</p>
                <p className="text-xl font-semibold text-slate-800">{card.value ?? '-'}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Users tab */}
      {tab === 'users' && (
        <div className="rounded-lg bg-white shadow-sm">
          {/* Mobile cards */}
          <div className="block sm:hidden divide-y divide-gray-100">
            {users.map((u) => (
              <div key={u.id} className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{u.name || '-'}</p>
                    <p className="text-xs text-gray-500">{u.email}</p>
                  </div>
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === 'admin'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {u.role}
                  </span>
                </div>
                {u.companies && (
                  <p className="text-xs text-gray-400 truncate">{u.companies}</p>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => changeRole(u.id, u.role === 'admin' ? 'user' : 'admin')}
                    className="text-xs text-indigo-600 hover:text-indigo-800"
                  >
                    {u.role === 'admin' ? 'Υποβίβαση' : 'Admin'}
                  </button>
                  <button
                    onClick={() => deleteUser(u.id, u.email)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Διαγραφή
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-5 py-3">Χρήστης</th>
                  <th className="px-5 py-3">Email</th>
                  <th className="px-5 py-3">Ρόλος</th>
                  <th className="px-5 py-3">Εταιρείες</th>
                  <th className="px-5 py-3">Εγγραφή</th>
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-slate-700">{u.name || '-'}</td>
                    <td className="px-5 py-3 text-slate-600">{u.email}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          u.role === 'admin'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600 max-w-xs truncate">
                      {u.companies || '-'}
                    </td>
                    <td className="px-5 py-3 text-slate-500 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('el-GR') : '-'}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex gap-3">
                        <button
                          onClick={() =>
                            changeRole(u.id, u.role === 'admin' ? 'user' : 'admin')
                          }
                          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                        >
                          {u.role === 'admin' ? 'Υποβίβαση' : 'Κάνε Admin'}
                        </button>
                        <button
                          onClick={() => deleteUser(u.id, u.email)}
                          className="text-xs text-red-500 hover:text-red-700 font-medium"
                        >
                          Διαγραφή
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Companies tab */}
      {tab === 'companies' && (
        <div className="rounded-lg bg-white shadow-sm">
          {/* Mobile cards */}
          <div className="block sm:hidden divide-y divide-gray-100">
            {companies.map((c) => (
              <div key={c.id} className="p-4 space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-800">{c.name}</p>
                  <span className="text-xs text-gray-400">{c.aade_env}</span>
                </div>
                <p className="text-xs text-gray-500">ΑΦΜ: {c.afm}</p>
                {c.members && <p className="text-xs text-gray-400 truncate">{c.members}</p>}
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-5 py-3">Εταιρεία</th>
                  <th className="px-5 py-3">ΑΦΜ</th>
                  <th className="px-5 py-3">Περιβάλλον</th>
                  <th className="px-5 py-3">Μέλη</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((c) => (
                  <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-slate-700">{c.name}</td>
                    <td className="px-5 py-3 text-slate-600">{c.afm}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          c.aade_env === 'prod'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {c.aade_env === 'prod' ? 'Παραγωγή' : 'Δοκιμαστικό'}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600 max-w-xs truncate">
                      {c.members || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
