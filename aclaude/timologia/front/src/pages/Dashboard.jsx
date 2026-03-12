import { useState, useEffect } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'

const fmt = (n) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR' }).format(n || 0)

export default function Dashboard() {
  const { activeCompanyId } = useCompany()
  const [stats, setStats] = useState({ revenue: 0, vat: 0, count: 0 })
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeCompanyId) return
    setLoading(true)

    Promise.all([
      apiJson(`/api/invoices?company_id=${activeCompanyId}&limit=5`),
      apiJson(`/api/invoices/stats?company_id=${activeCompanyId}`).catch(() => null),
    ])
      .then(([invData, statsData]) => {
        const list = invData.invoices || invData || []
        setInvoices(list)

        if (statsData) {
          setStats({
            revenue: statsData.monthly_revenue || 0,
            vat: statsData.monthly_vat || 0,
            count: statsData.monthly_count || 0,
          })
        } else {
          // Calculate from invoices as fallback
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
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeCompanyId])

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
    { label: 'Πλήθος Τιμολογίων', value: String(stats.count), color: 'bg-amber-500' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Αρχική</h1>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
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
          <h2 className="font-semibold text-slate-700">Πρόσφατα Τιμολόγια</h2>
        </div>

        {loading ? (
          <div className="flex h-32 items-center justify-center text-gray-400">Φόρτωση...</div>
        ) : invoices.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-gray-400">
            Δεν βρέθηκαν τιμολόγια
          </div>
        ) : (
          <div className="overflow-x-auto">
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
        )}
      </div>
    </div>
  )
}
