import { useCompany } from '../context/CompanyContext'

export default function CompanySelector() {
  const { companies, activeCompanyId, selectCompany, loading } = useCompany()

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

  if (companies.length === 0) {
    return <span className="text-sm text-gray-400">Καμία εταιρεία</span>
  }

  return (
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
  )
}
