import { useState, useEffect, useCallback } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import InvoiceTable from '../components/InvoiceTable'

const LIMIT = 50

export default function Invoices() {
  const { activeCompanyId } = useCompany()
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
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
      limit: LIMIT,
      sort: sortKey,
      sort_dir: sortDir,
    })
    if (direction) params.set('direction', direction)
    if (search) params.set('search', search)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)

    apiJson(`/api/invoices?${params}`)
      .then((data) => {
        setInvoices(data.invoices || data || [])
        setTotal(data.total || 0)
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
      <h1 className="text-2xl font-bold text-slate-800">Τιμολόγια</h1>

      {/* Filters */}
      <div className="rounded-lg bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Κατεύθυνση</label>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
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
              className="rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Έως</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>

          <form onSubmit={handleSearch} className="flex gap-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Αναζήτηση</label>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="ΑΦΜ, επωνυμία..."
                className="rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
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
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
            <p className="text-sm text-gray-500">
              Σελίδα {page} από {totalPages} ({total} τιμολόγια)
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Προηγούμενη
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
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Επόμενη
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
