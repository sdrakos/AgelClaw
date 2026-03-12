import { useState } from 'react'
import { api } from '../lib/api'

export default function ConfirmationCard({ confirmation, onResult }) {
  const [loading, setLoading] = useState(false)
  const { id, action_type, preview } = confirmation

  const ACTION_LABELS = {
    send_invoice: 'Αποστολή Τιμολογίου',
    cancel_invoice: 'Ακύρωση Τιμολογίου',
    generate_report: 'Δημιουργία Αναφοράς',
  }

  const handleAction = async (action) => {
    setLoading(true)
    try {
      const endpoint = action === 'confirm'
        ? `/api/chat/confirm/${id}`
        : `/api/chat/reject/${id}`
      const res = await api(endpoint, { method: 'POST' })
      const data = await res.json()
      onResult?.(action, data)
    } catch (err) {
      onResult?.('error', { error: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <svg className="h-5 w-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <span className="font-medium text-amber-800">
          {ACTION_LABELS[action_type] || action_type || 'Επιβεβαίωση Ενέργειας'}
        </span>
      </div>

      {preview && (
        <div className="mb-3 rounded-md bg-white/60 p-3 text-sm text-slate-700">
          {typeof preview === 'string' ? (
            <p>{preview}</p>
          ) : (
            <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(preview, null, 2)}</pre>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => handleAction('confirm')}
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          Επιβεβαίωση
        </button>
        <button
          onClick={() => handleAction('reject')}
          disabled={loading}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
        >
          Ακύρωση
        </button>
      </div>
    </div>
  )
}
