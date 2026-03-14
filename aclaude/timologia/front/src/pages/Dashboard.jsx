import { useState, useEffect } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'

const fmt = (n) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR' }).format(n || 0)

function AddCompanyForm({ onCreated }) {
  const [name, setName] = useState('')
  const [afm, setAfm] = useState('')
  const [aadeUser, setAadeUser] = useState('')
  const [aadeKey, setAadeKey] = useState('')
  const [aadeEnv, setAadeEnv] = useState('dev')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

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
      onCreated(data)
    } catch {
      setError('Σφάλμα δημιουργίας')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <div className="rounded-2xl bg-white p-8 shadow-sm">
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
            <label className="mb-1 block text-sm font-medium text-slate-700">AADE User ID *</label>
            <input type="text" value={aadeUser} onChange={(e) => setAadeUser(e.target.value)} required
              placeholder="Από myDATA → Διαχείριση Συνδρομών"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">AADE Subscription Key *</label>
            <input type="password" value={aadeKey} onChange={(e) => setAadeKey(e.target.value)} required
              placeholder="Από myDATA → Διαχείριση Συνδρομών"
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
          <button type="submit" disabled={saving}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {saving ? 'Δημιουργία...' : 'Δημιουργία Εταιρείας'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { activeCompanyId, companies, addCompany } = useCompany()
  const [stats, setStats] = useState({ revenue: 0, vat: 0, count: 0 })
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeCompanyId) return
    setLoading(true)

    apiJson(`/api/invoices?company_id=${activeCompanyId}&per_page=5`)
      .then((data) => {
        const list = data.items || data.invoices || []
        setInvoices(list)

        // Calculate stats from invoices
        const now = new Date()
        const thisMonth = list.filter((inv) => {
          const d = new Date(inv.issue_date || inv.date)
          return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
        })
        setStats({
          revenue: thisMonth.reduce((s, i) => s + (i.net_amount || 0), 0),
          vat: thisMonth.reduce((s, i) => s + (i.vat_amount || 0), 0),
          count: thisMonth.length,
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeCompanyId])

  if (!activeCompanyId && companies.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-800">Αρχική</h1>
        <AddCompanyForm onCreated={(c) => {
          addCompany(c)
        }} />
      </div>
    )
  }

  if (!activeCompanyId) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  const STAT_CARDS = [
    { label: 'Μηνιαίος Τζίρος', value: fmt(stats.revenue), color: 'bg-indigo-500' },
    { label: 'ΦΠΑ Μήνα', value: fmt(stats.vat), color: 'bg-emerald-500' },
    { label: 'Πλήθος Παραστατικών', value: String(stats.count), color: 'bg-amber-500' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Αρχική</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {STAT_CARDS.map((card) => (
          <div key={card.label} className="rounded-lg bg-white p-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className={`h-10 w-10 rounded-lg ${card.color} flex items-center justify-center`}>
                <div className="h-5 w-5 rounded-full bg-white/30" />
              </div>
              <div>
                <p className="text-sm text-gray-500">{card.label}</p>
                <p className="text-xl font-semibold text-slate-800">
                  {loading ? '...' : card.value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent invoices */}
      <div className="rounded-lg bg-white shadow-sm">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-semibold text-slate-700">Πρόσφατα Παραστατικά</h2>
        </div>

        {loading ? (
          <div className="flex h-32 items-center justify-center text-gray-400">Φόρτωση...</div>
        ) : invoices.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-gray-400">
            Δεν βρέθηκαν παραστατικά
          </div>
        ) : (
          <>
          {/* Mobile card view */}
          <div className="block sm:hidden divide-y divide-gray-100">
            {invoices.map((inv) => (
              <div key={inv.id || inv.mark} className="p-4 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">{inv.issue_date || inv.date || '-'}</span>
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      inv.direction === 'sent'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-orange-100 text-orange-700'
                    }`}
                  >
                    {inv.direction === 'sent' ? 'Εκδοθέν' : 'Ληφθέν'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-600 truncate mr-4">
                    {inv.counterpart_name || inv.counterpart_afm || '-'}
                  </p>
                  <span className="text-sm font-semibold text-slate-800 whitespace-nowrap">
                    {fmt(inv.total_amount || inv.gross_amount)}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table view */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-5 py-3">Ημ/νία</th>
                  <th className="px-5 py-3">Σειρά/ΑΑ</th>
                  <th className="px-5 py-3">Αντισυμβαλλόμενος</th>
                  <th className="px-5 py-3 text-right">Σύνολο</th>
                  <th className="px-5 py-3">Κατεύθυνση</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id || inv.mark} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 text-slate-600">
                      {inv.issue_date || inv.date || '-'}
                    </td>
                    <td className="px-5 py-3 font-medium text-slate-700">
                      {inv.series || ''}{inv.aa ? `/${inv.aa}` : ''}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {inv.counterpart_name || inv.counterpart_afm || '-'}
                    </td>
                    <td className="px-5 py-3 text-right font-medium text-slate-700">
                      {fmt(inv.total_amount || inv.gross_amount)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          inv.direction === 'sent'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-orange-100 text-orange-700'
                        }`}
                      >
                        {inv.direction === 'sent' ? 'Εκδοθέν' : 'Ληφθέν'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
