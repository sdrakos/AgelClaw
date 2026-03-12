import { useState, useEffect } from 'react'
import { api, apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'

const PRESETS = [
  { key: 'daily_summary', label: 'Ημερήσια Σύνοψη', desc: 'Τιμολόγια ημέρας + σύνοψη' },
  { key: 'monthly_vat', label: 'Μηνιαίο ΦΠΑ', desc: 'Ανάλυση ΦΠΑ μήνα' },
  { key: 'quarterly_income', label: 'Τριμηνιαία Έσοδα', desc: 'Σύνοψη εσόδων τριμήνου' },
  { key: 'annual_overview', label: 'Ετήσια Επισκόπηση', desc: 'Ολική εικόνα χρήσης' },
  { key: 'custom', label: 'Προσαρμοσμένη', desc: 'Επιλέξτε παραμέτρους' },
]

const CRON_OPTIONS = [
  { label: 'Καθημερινά', prefix: 'daily', hasDay: false },
  { label: 'Εβδομαδιαία', prefix: 'weekly', hasDay: true },
  { label: 'Μηνιαία', prefix: 'monthly', hasDay: false },
]

const DAYS = ['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']

export default function Reports() {
  const { activeCompanyId } = useCompany()
  const [generating, setGenerating] = useState(null)
  const [genError, setGenError] = useState('')
  const [schedules, setSchedules] = useState([])
  const [loadingSchedules, setLoadingSchedules] = useState(true)
  const [showScheduleForm, setShowScheduleForm] = useState(false)

  // Schedule form state
  const [schedPreset, setSchedPreset] = useState('daily_summary')
  const [schedFreq, setSchedFreq] = useState('daily')
  const [schedDay, setSchedDay] = useState(0)
  const [schedTime, setSchedTime] = useState('09:00')
  const [schedRecipients, setSchedRecipients] = useState('')

  useEffect(() => {
    if (!activeCompanyId) return
    setLoadingSchedules(true)
    apiJson(`/api/reports/schedules?company_id=${activeCompanyId}`)
      .then((data) => setSchedules(data.schedules || data || []))
      .catch(() => setSchedules([]))
      .finally(() => setLoadingSchedules(false))
  }, [activeCompanyId])

  const generateReport = async (preset) => {
    setGenerating(preset)
    setGenError('')
    try {
      const data = await apiJson('/api/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ company_id: activeCompanyId, preset }),
      })

      if (data.error) {
        setGenError(data.error)
        return
      }

      // Download the file
      if (data.report_id || data.id) {
        const id = data.report_id || data.id
        const res = await api(`/api/reports/download/${id}`)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = data.filename || `report_${preset}.xlsx`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch {
      setGenError('Σφάλμα δημιουργίας αναφοράς')
    } finally {
      setGenerating(null)
    }
  }

  const createSchedule = async (e) => {
    e.preventDefault()
    let cron = ''
    if (schedFreq === 'daily') cron = `daily_${schedTime}`
    else if (schedFreq === 'weekly') cron = `weekly_${schedDay}_${schedTime}`
    else if (schedFreq === 'monthly') cron = `monthly_1_${schedTime}`

    try {
      const data = await apiJson('/api/reports/schedules', {
        method: 'POST',
        body: JSON.stringify({
          company_id: activeCompanyId,
          preset: schedPreset,
          cron,
          recipients: schedRecipients,
        }),
      })
      if (data.error) {
        setGenError(data.error)
        return
      }
      setSchedules((prev) => [...prev, data.schedule || data])
      setShowScheduleForm(false)
    } catch {
      setGenError('Σφάλμα δημιουργίας χρονοπρογράμματος')
    }
  }

  const toggleSchedule = async (id, enabled) => {
    try {
      await apiJson(`/api/reports/schedules/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !enabled }),
      })
      setSchedules((prev) =>
        prev.map((s) => (s.id === id ? { ...s, enabled: !enabled } : s))
      )
    } catch {}
  }

  const deleteSchedule = async (id) => {
    try {
      await api(`/api/reports/schedules/${id}`, { method: 'DELETE' })
      setSchedules((prev) => prev.filter((s) => s.id !== id))
    } catch {}
  }

  if (!activeCompanyId) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Αναφορές</h1>

      {genError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{genError}</div>
      )}

      {/* Generate now */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-700">Εκτέλεση Τώρα</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PRESETS.map((p) => (
            <div key={p.key} className="rounded-lg bg-white p-5 shadow-sm">
              <h3 className="font-medium text-slate-800">{p.label}</h3>
              <p className="mt-1 text-sm text-gray-500">{p.desc}</p>
              <button
                onClick={() => generateReport(p.key)}
                disabled={generating !== null}
                className="mt-3 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {generating === p.key ? (
                  <span className="flex items-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                    Δημιουργία...
                  </span>
                ) : (
                  'Δημιουργία'
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Scheduled reports */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-700">Προγραμματισμένες</h2>
          <button
            onClick={() => setShowScheduleForm(!showScheduleForm)}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
          >
            {showScheduleForm ? 'Ακύρωση' : 'Νέο Πρόγραμμα'}
          </button>
        </div>

        {/* Schedule creation form */}
        {showScheduleForm && (
          <form onSubmit={createSchedule} className="mb-4 rounded-lg bg-white p-5 shadow-sm space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-600">Τύπος Αναφοράς</label>
                <select
                  value={schedPreset}
                  onChange={(e) => setSchedPreset(e.target.value)}
                  className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                >
                  {PRESETS.map((p) => (
                    <option key={p.key} value={p.key}>{p.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-600">Συχνότητα</label>
                <select
                  value={schedFreq}
                  onChange={(e) => setSchedFreq(e.target.value)}
                  className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                >
                  {CRON_OPTIONS.map((c) => (
                    <option key={c.prefix} value={c.prefix}>{c.label}</option>
                  ))}
                </select>
              </div>

              {schedFreq === 'weekly' && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-600">Ημέρα</label>
                  <select
                    value={schedDay}
                    onChange={(e) => setSchedDay(Number(e.target.value))}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  >
                    {DAYS.map((d, i) => (
                      <option key={i} value={i}>{d}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-600">Ώρα</label>
                <input
                  type="time"
                  value={schedTime}
                  onChange={(e) => setSchedTime(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium text-gray-600">Παραλήπτες (email, κόμμα)</label>
                <input
                  type="text"
                  value={schedRecipients}
                  onChange={(e) => setSchedRecipients(e.target.value)}
                  placeholder="user@example.com, other@example.com"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Αποθήκευση
            </button>
          </form>
        )}

        {/* Schedules table */}
        <div className="rounded-lg bg-white shadow-sm">
          {loadingSchedules ? (
            <div className="flex h-24 items-center justify-center text-gray-400">Φόρτωση...</div>
          ) : schedules.length === 0 ? (
            <div className="flex h-24 items-center justify-center text-gray-400">
              Δεν υπάρχουν προγραμματισμένες αναφορές
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-100 text-left text-xs font-medium uppercase text-gray-500">
                    <th className="px-4 py-3">Τύπος</th>
                    <th className="px-4 py-3">Χρονοπρόγραμμα</th>
                    <th className="px-4 py-3">Παραλήπτες</th>
                    <th className="px-4 py-3">Κατάσταση</th>
                    <th className="px-4 py-3">Ενέργειες</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-slate-700">
                        {PRESETS.find((p) => p.key === s.preset)?.label || s.preset}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{s.cron}</td>
                      <td className="px-4 py-3 text-slate-600 max-w-[200px] truncate">{s.recipients}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => toggleSchedule(s.id, s.enabled)}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                            s.enabled ? 'bg-indigo-600' : 'bg-gray-300'
                          }`}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                              s.enabled ? 'translate-x-4.5' : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => deleteSchedule(s.id)}
                          className="text-red-500 hover:text-red-700 text-xs font-medium"
                        >
                          Διαγραφή
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
