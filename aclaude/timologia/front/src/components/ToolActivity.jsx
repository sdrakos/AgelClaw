export default function ToolActivity({ tool }) {
  const label = tool?.name || 'Επεξεργασία'
  const TOOL_LABELS = {
    search_invoices: 'Αναζήτηση τιμολογίων',
    fetch_aade: 'Ανάκτηση από ΑΑΔΕ',
    generate_xml: 'Δημιουργία XML',
    send_invoice: 'Αποστολή τιμολογίου',
    calculate_vat: 'Υπολογισμός ΦΠΑ',
  }

  return (
    <div className="flex items-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      <span>{TOOL_LABELS[label] || label}...</span>
    </div>
  )
}
