import { useState, useEffect } from 'react'
import { api, apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'

const PRESETS = [
  { key: 'daily_summary', label: 'Ημερήσια Σύνοψη', desc: 'Παραστατικά ημέρας + σύνοψη' },
  { key: 'monthly_vat', label: 'Μηνιαίο ΦΠΑ', desc: 'Ανάλυση ΦΠΑ μήνα' },
  { key: 'quarterly_income', label: 'Τριμηνιαία Έσοδα', desc: 'Σύνοψη εσόδων τριμήνου' },
  { key: 'expenses_by_supplier', label: 'Έξοδα ανά Προμηθευτή', desc: 'Ανάλυση εξόδων ανά προμηθευτή' },
  { key: 'annual_overview', label: 'Ετήσια Επισκόπηση', desc: 'Ολική εικόνα χρήσης' },
  { key: 'custom', label: 'Προσαρμοσμένη', desc: 'Επιλέξτε παραμέτρους' },
]

const CRON_OPTIONS = [
  { label: 'Καθημερινά', prefix: 'daily', hasDay: false },
  { label: 'Εβδομαδιαία', prefix: 'weekly', hasDay: true },
  { label: 'Μηνιαία', prefix: 'monthly', hasDay: false },
]

const DAYS = ['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']

const PERIOD_OPTIONS = [
  { value: 'today', label: 'Σήμερα' },
  { value: 'yesterday', label: 'Χθες' },
  { value: 'last_7_days', label: 'Τελευταίες 7 ημέρες' },
  { value: 'last_30_days', label: 'Τελευταίες 30 ημέρες' },
  { value: 'current_month', label: 'Τρέχων μήνας' },
  { value: 'previous_month', label: 'Προηγούμενος μήνας' },
  { value: 'current_quarter', label: 'Τρέχον τρίμηνο' },
  { value: 'current_year', label: 'Τρέχον έτος' },
]

const DIRECTION_OPTIONS = [
  { value: 'all', label: 'Όλα (Έσοδα + Έξοδα)' },
  { value: 'sent', label: 'Μόνο Έσοδα' },
  { value: 'received', label: 'Μόνο Έξοδα' },
]

export default function Reports() {
  const { activeCompanyId } = useCompany()
  const [generating, setGenerating] = useState(null)
  const [genError, setGenError] = useState('')
  const [genSuccess, setGenSuccess] = useState('')
  const [schedules, setSchedules] = useState([])
  const [loadingSchedules, setLoadingSchedules] = useState(true)
  const [showScheduleForm, setShowScheduleForm] = useState(false)

  // Date range modal state (for presets that need date selection)
  const [dateModal, setDateModal] = useState(null) // preset key
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // Email modal state
  const [emailModal, setEmailModal] = useState(null) // { reportId, filename }
  const [emailTo, setEmailTo] = useState('')
  const [emailSending, setEmailSending] = useState(false)

  // Schedule form state
  const [schedPreset, setSchedPreset] = useState('daily_summary')
  const [schedFreq, setSchedFreq] = useState('daily')
  const [schedDay, setSchedDay] = useState(0)
  const [schedTime, setSchedTime] = useState('09:00')
  const [schedRecipients, setSchedRecipients] = useState('')
  const [schedPeriod, setSchedPeriod] = useState('current_month')
  const [schedDirection, setSchedDirection] = useState('all')

  useEffect(() => {
    if (!activeCompanyId) return
    setLoadingSchedules(true)
    apiJson(`/api/reports/schedules?company_id=${activeCompanyId}`)
      .then((data) => setSchedules(data.schedules || data || []))
      .catch(() => setSchedules([]))
      .finally(() => setLoadingSchedules(false))
  }, [activeCompanyId])

  const NEEDS_DATES = ['expenses_by_supplier', 'custom']

  const handleGenerateClick = (preset) => {
    if (NEEDS_DATES.includes(preset)) {
      setDateModal(preset)
      setDateFrom('')
      setDateTo('')
    } else {
      generateReport(preset)
    }
  }

  const handleDateSubmit = (e) => {
    e.preventDefault()
    if (!dateFrom || !dateTo) return
    const preset = dateModal
    setDateModal(null)
    generateReport(preset, { date_from: dateFrom, date_to: dateTo })
  }

  const generateReport = async (preset, params = {}) => {
    setGenerating(preset)
    setGenError('')
    setGenSuccess('')
    try {
      const data = await apiJson('/api/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ company_id: activeCompanyId, preset, params }),
      })

      if (data.error) {
        setGenError(data.error)
        return
      }

      const id = data.report_id || data.id
      const filename = data.filename || `report_${preset}.xlsx`

      // Download the file
      if (id) {
        const res = await api(`/api/reports/download/${id}`)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
      }

      // Show email option
      setGenSuccess(JSON.stringify({ id, filename }))
    } catch {
      setGenError('Σφάλμα δημιουργίας αναφοράς')
    } finally {
      setGenerating(null)
    }
  }

  const sendReportEmail = async (e) => {
    e.preventDefault()
    if (!emailModal || !emailTo.trim()) return
    setEmailSending(true)
    setGenError('')
    try {
      const data = await apiJson(`/api/reports/${emailModal.reportId}/email`, {
        method: 'POST',
        body: JSON.stringify({ to: emailTo.split(',').map((e) => e.trim()).filter(Boolean) }),
      })
      if (data.success) {
        setGenSuccess('')
        setEmailModal(null)
        setEmailTo('')
        setGenError('')
        alert('Email στάλθηκε!')
      } else {
        setGenError(data.error || 'Σφάλμα αποστολής')
      }
    } catch {
      setGenError('Σφάλμα αποστολής email')
    } finally {
      setEmailSending(false)
    }
  }

  const createSchedule = async (e) => {
    e.preventDefault()
    let cron = ''
    if (schedFreq === 'daily') cron = `daily_${schedTime}`
    else if (schedFreq === 'weekly') cron = `weekly_${schedDay}_${schedTime}`
    else if (schedFreq === 'monthly') cron = `monthly_1_${schedTime}`

    // Build params for custom/expenses_by_supplier presets
    const params = {}
    if (schedPreset === 'custom' || schedPreset === 'expenses_by_supplier') {
      params.period = schedPeriod
      params.direction = schedDirection
    }

    try {
      const data = await apiJson('/api/reports/schedules', {
        method: 'POST',
        body: JSON.stringify({
          company_id: activeCompanyId,
          preset: schedPreset,
          params,
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

      {/* Success bar with email option */}
      {genSuccess && (() => {
        const info = JSON.parse(genSuccess)
        return (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
            <div className="flex items-center gap-2">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Η αναφορά <b>{info.filename}</b> κατέβηκε.</span>
            </div>
            <button
              onClick={() => { setEmailModal({ reportId: info.id, filename: info.filename }); setEmailTo('') }}
              className="flex items-center gap-1 rounded-md bg-green-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-800 transition-colors"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Αποστολή Email
            </button>
          </div>
        )
      })()}

      {/* Email modal */}
      {emailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEmailModal(null)}>
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-800">Αποστολή Αναφοράς</h3>
            <p className="mt-1 text-sm text-gray-500">{emailModal.filename}</p>
            <form onSubmit={sendReportEmail} className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-600">Παραλήπτες (κόμμα)</label>
                <input
                  type="text"
                  value={emailTo}
                  onChange={(e) => setEmailTo(e.target.value)}
                  placeholder="user@example.com, other@example.com"
                  autoFocus
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setEmailModal(null)}
                  className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                  Ακύρωση
                </button>
                <button type="submit" disabled={emailSending || !emailTo.trim()}
                  className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  {emailSending ? 'Αποστολή...' : 'Αποστολή'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Date range modal */}
      {dateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDateModal(null)}>
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-800">Επιλογή Περιόδου</h3>
            <p className="mt-1 text-sm text-gray-500">
              {PRESETS.find((p) => p.key === dateModal)?.label}
            </p>
            <form onSubmit={handleDateSubmit} className="mt-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-600">Από</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    required
                    autoFocus
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-600">Έως</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    required
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setDateModal(null)}
                  className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                  Ακύρωση
                </button>
                <button type="submit" disabled={!dateFrom || !dateTo}
                  className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  Δημιουργία
                </button>
              </div>
            </form>
          </div>
        </div>
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
                onClick={() => handleGenerateClick(p.key)}
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

              {(schedPreset === 'custom' || schedPreset === 'expenses_by_supplier') && (
                <>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-600">Περίοδος</label>
                    <select
                      value={schedPeriod}
                      onChange={(e) => setSchedPeriod(e.target.value)}
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                      {PERIOD_OPTIONS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-600">Κατεύθυνση</label>
                    <select
                      value={schedDirection}
                      onChange={(e) => setSchedDirection(e.target.value)}
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                      {DIRECTION_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}

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
            {/* Mobile card view */}
            <div className="block sm:hidden divide-y divide-gray-100">
              {schedules.map((s) => {
                const sp = typeof s.params === 'string' ? (() => { try { return JSON.parse(s.params) } catch { return {} } })() : (s.params || {})
                const periodLabel = PERIOD_OPTIONS.find((p) => p.value === sp.period)?.label
                const dirLabel = DIRECTION_OPTIONS.find((d) => d.value === sp.direction)?.label
                return (
                  <div key={s.id} className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-slate-700 text-sm">
                          {PRESETS.find((p) => p.key === s.preset)?.label || s.preset}
                        </p>
                        {(periodLabel || dirLabel) && (
                          <p className="text-xs text-slate-400 mt-0.5">
                            {[periodLabel, dirLabel].filter(Boolean).join(' · ')}
                          </p>
                        )}
                      </div>
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
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-slate-500">{s.cron}</span>
                      <button
                        onClick={() => deleteSchedule(s.id)}
                        className="rounded px-2 py-1 text-xs font-medium text-red-500 hover:bg-red-50 hover:text-red-700 transition-colors"
                      >
                        Διαγραφή
                      </button>
                    </div>
                    {s.recipients && (
                      <p className="text-xs text-slate-400 truncate">{s.recipients}</p>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Desktop table view */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead>
                  <tr className="border-b bg-gray-100 text-left text-xs font-medium uppercase text-gray-500">
                    <th className="whitespace-nowrap px-4 py-3">Τύπος</th>
                    <th className="whitespace-nowrap px-4 py-3">Χρονοπρόγραμμα</th>
                    <th className="whitespace-nowrap px-4 py-3">Παραλήπτες</th>
                    <th className="whitespace-nowrap px-4 py-3 w-20 text-center">Κατάσταση</th>
                    <th className="whitespace-nowrap px-4 py-3 w-24 text-center">Ενέργειες</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => {
                    const sp = typeof s.params === 'string' ? (() => { try { return JSON.parse(s.params) } catch { return {} } })() : (s.params || {})
                    const periodLabel = PERIOD_OPTIONS.find((p) => p.value === sp.period)?.label
                    const dirLabel = DIRECTION_OPTIONS.find((d) => d.value === sp.direction)?.label
                    return (
                    <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-700 whitespace-nowrap">
                          {PRESETS.find((p) => p.key === s.preset)?.label || s.preset}
                        </div>
                        {(periodLabel || dirLabel) && (
                          <div className="text-xs text-slate-400 mt-0.5">
                            {[periodLabel, dirLabel].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-600">{s.cron}</td>
                      <td className="px-4 py-3 text-slate-600 max-w-[250px] truncate" title={s.recipients}>
                        {s.recipients}
                      </td>
                      <td className="px-4 py-3 text-center">
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
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        <button
                          onClick={() => deleteSchedule(s.id)}
                          className="rounded px-2 py-1 text-xs font-medium text-red-500 hover:bg-red-50 hover:text-red-700 transition-colors"
                        >
                          Διαγραφή
                        </button>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
