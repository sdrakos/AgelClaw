import { useState } from 'react'

const fmt = (n) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR' }).format(n || 0)

const COLUMNS = [
  { key: 'issue_date', label: 'Ημ/νία' },
  { key: 'series_aa', label: 'Σειρά/ΑΑ' },
  { key: 'type_description', label: 'Τύπος' },
  { key: 'counterpart_name', label: 'Αντισυμβαλλόμενος' },
  { key: 'net_amount', label: 'Καθαρό', align: 'right' },
  { key: 'vat_amount', label: 'ΦΠΑ', align: 'right' },
  { key: 'total_amount', label: 'Σύνολο', align: 'right' },
  { key: 'direction', label: 'Κατεύθυνση' },
]

export default function InvoiceTable({ invoices, loading, sortKey, sortDir, onSort }) {
  const handleSort = (key) => {
    if (onSort) onSort(key)
  }

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-gray-400">
        <svg className="mr-2 h-5 w-5 animate-spin" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Φόρτωση τιμολογίων...
      </div>
    )
  }

  if (!invoices || invoices.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-gray-400">
        Δεν βρέθηκαν τιμολόγια
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-100 text-left text-xs font-medium uppercase text-gray-500">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className={`cursor-pointer select-none px-4 py-3 hover:text-gray-700 ${
                  col.align === 'right' ? 'text-right' : ''
                }`}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    <span className="text-indigo-500">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv, idx) => (
            <tr key={inv.id || inv.mark || idx} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-slate-600">{inv.issue_date || inv.date || '-'}</td>
              <td className="px-4 py-3 font-medium text-slate-700">
                {inv.series || ''}{inv.aa ? `/${inv.aa}` : ''}
              </td>
              <td className="px-4 py-3 text-slate-600 max-w-[200px] truncate">
                {inv.type_description || inv.invoice_type || '-'}
              </td>
              <td className="px-4 py-3 text-slate-600 max-w-[200px] truncate">
                {inv.counterpart_name || inv.counterpart_afm || '-'}
              </td>
              <td className="px-4 py-3 text-right font-medium text-slate-700">{fmt(inv.net_amount)}</td>
              <td className="px-4 py-3 text-right text-slate-600">{fmt(inv.vat_amount)}</td>
              <td className="px-4 py-3 text-right font-semibold text-slate-800">{fmt(inv.total_amount || inv.gross_amount)}</td>
              <td className="px-4 py-3">
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
  )
}
