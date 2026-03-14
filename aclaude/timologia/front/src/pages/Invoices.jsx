import { useState, useEffect, useCallback } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import InvoiceTable from '../components/InvoiceTable'

const LIMIT = 50
const fmt = (n) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR' }).format(n || 0)

export default function Invoices() {
  const { activeCompanyId } = useCompany()
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [summary, setSummary] = useState(null)
  const [direction, setDirection] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortKey, setSortKey] = useState('issue_date')
  const [sortDir, setSortDir] = useState('desc')

  const fetchInvoices = useCallback(() => {
    if (!activeCompanyId) return
    setLoading(true)

    const params = new URLSearchParams({
      company_id: activeCompanyId,
      page,
      per_page: LIMIT,
    })
    if (direction) params.set('direction', direction)
    if (search) params.set('search', search)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)

    apiJson(`/api/invoices?${params}`)
      .then((data) => {
        setInvoices(data.items || data.invoices || [])
        setTotal(data.total || 0)
        setSummary(data.summary || null)
      })
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false))
  }, [activeCompanyId, page, direction, search, dateFrom, dateTo, sortKey, sortDir])

  useEffect(() => {
    fetchInvoices()
  }, [fetchInvoices])

  useEffect(() => {
    setPage(1)
  }, [direction, search, dateFrom, dateTo, activeCompanyId])

  const handleSort = (key) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setSearch(searchInput)
  }

  const totalPages = Math.max(1, Math.ceil(total / LIMIT))

  if (!activeCompanyId) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-800">Παραστατικά</h1>

      {/* Filters */}
      <div className="rounded-lg bg-white p-4 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:flex lg:flex-wrap items-end gap-3">
          <div className="col-span-2 sm:col-span-1">
            <label className="mb-1 block text-xs font-medium text-gray-500">Κατεύθυνση</label>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              className="w-full lg:w-auto rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            >
              <option value="">Όλα</option>
              <option value="sent">Εκδοθέντα</option>
              <option value="received">Ληφθέντα</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Από</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full lg:w-auto rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Έως</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full lg:w-auto rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>

          <form onSubmit={handleSearch} className="col-span-2 sm:col-span-1 flex gap-2">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-gray-500">Αναζήτηση</label>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="ΑΦΜ, επωνυμία..."
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
              />
            </div>
            <button
              type="submit"
              className="mt-auto rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Εύρεση
            </button>
          </form>
        </div>
      </div>

      {/* Summary */}
      {summary && !loading && total > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div className="rounded-lg bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-gray-500">Πλήθος</p>
            <p className="text-lg font-semibold text-slate-800">{total}</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-4 shadow-sm">
            <p className="text-xs font-medium text-blue-600">Εκδοθέντα (καθαρά)</p>
            <p className="text-lg font-semibold text-blue-700">{fmt(summary.sent_net)}</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-4 shadow-sm">
            <p className="text-xs font-medium text-blue-600">ΦΠΑ Εκδοθέντων</p>
            <p className="text-lg font-semibold text-blue-700">{fmt(summary.sent_vat)}</p>
          </div>
          <div className="rounded-lg bg-orange-50 p-4 shadow-sm">
            <p className="text-xs font-medium text-orange-600">Ληφθέντα (καθαρά)</p>
            <p className="text-lg font-semibold text-orange-700">{fmt(summary.received_net)}</p>
          </div>
          <div className="rounded-lg bg-orange-50 p-4 shadow-sm">
            <p className="text-xs font-medium text-orange-600">ΦΠΑ Ληφθέντων</p>
            <p className="text-lg font-semibold text-orange-700">{fmt(summary.received_vat)}</p>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg bg-white shadow-sm">
        <InvoiceTable
          invoices={invoices}
          loading={loading}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
        />

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-gray-100 px-4 py-3">
            <p className="text-sm text-gray-500">
              Σελίδα {page}/{totalPages} ({total})
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-md border border-gray-300 px-2 sm:px-3 py-1.5 text-sm text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <span className="hidden sm:inline">Προηγούμενη</span>
                <span className="sm:hidden">&larr;</span>
              </button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const start = Math.max(1, Math.min(page - 2, totalPages - 4))
                const p = start + i
                if (p > totalPages) return null
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                      p === page
                        ? 'bg-indigo-600 text-white'
                        : 'border border-gray-300 text-slate-600 hover:bg-gray-50'
                    }`}
                  >
                    {p}
                  </button>
                )
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded-md border border-gray-300 px-2 sm:px-3 py-1.5 text-sm text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <span className="hidden sm:inline">Επόμενη</span>
                <span className="sm:hidden">&rarr;</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
