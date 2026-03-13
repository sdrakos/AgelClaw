import { useState, useEffect } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const fmt = (n) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR' }).format(n || 0)

const fmtK = (n) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}K` : n?.toFixed(0) || '0'

const pctChange = (current, previous) => {
  if (!previous) return null
  return ((current - previous) / previous * 100).toFixed(1)
}

const VAT_COLORS = ['#4f46e5', '#10b981', '#f59e0b', '#94a3b8']

function Card({ title, children, full }) {
  return (
    <div className={`rounded-lg bg-white p-5 shadow-sm${full ? ' col-span-full' : ''}`}>
      {title && <h3 className="mb-4 text-base font-semibold text-slate-800">{title}</h3>}
      {children}
    </div>
  )
}

function ComparisonCard({ label, current, previous }) {
  const pct = pctChange(current?.gross, previous?.gross)
  const isUp = pct !== null && parseFloat(pct) >= 0
  return (
    <div className="flex-1 rounded-lg border border-slate-100 bg-slate-50 p-4">
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-2xl font-bold text-slate-800">{fmt(current?.gross)}</p>
      {pct !== null && (
        <div className="mt-1 flex items-center gap-1">
          <span className={`text-sm font-medium ${isUp ? 'text-emerald-600' : 'text-rose-600'}`}>
            {isUp ? '\u2191' : '\u2193'} {Math.abs(parseFloat(pct))}%
          </span>
          <span className="text-xs text-slate-400">vs {fmt(previous?.gross)}</span>
        </div>
      )}
      <p className="mt-1 text-xs text-slate-400">{current?.count || 0} παραστατικά</p>
    </div>
  )
}

function CurrencyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-100 bg-white px-3 py-2 shadow-md">
      <p className="mb-1 text-xs font-medium text-slate-500">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="text-sm" style={{ color: entry.color }}>
          {entry.name}: {fmt(entry.value)}
        </p>
      ))}
    </div>
  )
}

function PieTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="rounded-lg border border-slate-100 bg-white px-3 py-2 shadow-md">
      <p className="text-sm font-medium text-slate-700">ΦΠΑ {d.payload.rate}%</p>
      <p className="text-sm text-slate-600">Καθαρό: {fmt(d.payload.net)}</p>
      <p className="text-sm text-slate-600">ΦΠΑ: {fmt(d.payload.vat)}</p>
      <p className="text-xs text-slate-400">{d.payload.count} παραστατικά</p>
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex min-h-[300px] items-center justify-center">
      <svg className="h-8 w-8 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
    </div>
  )
}

export default function Analytics() {
  const { activeCompanyId } = useCompany()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activeCompanyId) { setData(null); return }
    let cancelled = false
    setLoading(true)
    setError('')
    apiJson(`/api/analytics?company_id=${activeCompanyId}`)
      .then((res) => {
        if (cancelled) return
        if (res.error) { setError(res.error); setData(null) }
        else setData(res)
      })
      .catch(() => { if (!cancelled) setError('Σφάλμα φόρτωσης δεδομένων') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [activeCompanyId])

  if (!activeCompanyId) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <p className="text-slate-400">Επιλέξτε εταιρεία</p>
      </div>
    )
  }

  if (loading) return <Spinner />

  if (error) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <p className="text-rose-500">{error}</p>
      </div>
    )
  }

  const pc = data?.period_comparison || {}
  const mf = data?.month_forecast || {}
  const dailyRev = data?.daily_revenue || []
  const vatBreak = data?.vat_breakdown || []
  const topSup = data?.top_suppliers || []
  const topCust = data?.top_customers || []
  const monthEvo = data?.monthly_evolution || []
  const avgInv = data?.avg_invoice_by_month || []
  const seasonal = data?.seasonality || []
  const weekday = data?.weekday_revenue || []

  const forecastPct = mf.days_total ? Math.round((mf.days_elapsed / mf.days_total) * 100) : 0

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Στατιστικη Αναλυση</h1>

      {/* 1. Period Comparison */}
      <Card full>
        <div className="flex flex-col gap-3 sm:flex-row">
          <ComparisonCard
            label="Τρεχων Μηνας vs Προηγουμενος"
            current={pc.current_month}
            previous={pc.prev_month}
          />
          <ComparisonCard
            label="Τρεχουσα Εβδομαδα vs Προηγουμενη"
            current={pc.current_week}
            previous={pc.prev_week}
          />
          <ComparisonCard
            label="Φετος vs Περυσι (YoY)"
            current={pc.yoy_current}
            previous={pc.yoy_previous}
          />
        </div>
      </Card>

      {/* 2. Month Forecast */}
      <Card title="Προβλεψη Μηνα" full>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-8">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Πραγματικά μέχρι τώρα</p>
            <p className="text-3xl font-bold text-slate-800">{fmt(mf.actual)}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Πρόβλεψη τέλους μήνα</p>
            <p className="text-2xl font-semibold text-indigo-600">{fmt(mf.projected)}</p>
          </div>
          <div className="flex-1">
            <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
              <span>Ημέρα {mf.days_elapsed || 0}/{mf.days_total || 0}</span>
              <span>{forecastPct}%</span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all"
                style={{ width: `${forecastPct}%` }}
              />
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 grid-cols-1 md:grid-cols-2">
        {/* 3. Daily Revenue */}
        <Card title="Μεσος Ημερησιος Τζιρος">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={dailyRev}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <Tooltip content={<CurrencyTooltip />} />
              <Legend />
              <Line type="monotone" dataKey="income" name="Έσοδα" stroke="#4f46e5" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="expenses" name="Έξοδα" stroke="#f43f5e" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* 4. VAT Breakdown */}
        <Card title="Αναλυση ΦΠΑ">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={vatBreak}
                dataKey="net"
                nameKey="rate"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ rate }) => `${rate}`}
              >
                {vatBreak.map((_, i) => (
                  <Cell key={i} fill={VAT_COLORS[i % VAT_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<PieTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* 5. Top Suppliers */}
        <Card title="Top Προμηθευτες">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topSup.slice(0, 10)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11 }}
                width={120}
                tickFormatter={(v, i) => {
                  const item = topSup[i]
                  const label = item?.name || item?.afm || v
                  return label.length > 18 ? label.slice(0, 18) + '...' : label
                }}
              />
              <Tooltip content={<CurrencyTooltip />} />
              <Bar dataKey="gross" name="Σύνολο" fill="#f43f5e" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 6. Top Customers */}
        <Card title="Top Πελατες">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topCust.slice(0, 10)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11 }}
                width={120}
                tickFormatter={(v, i) => {
                  const item = topCust[i]
                  const label = item?.name || item?.afm || v
                  return label.length > 18 ? label.slice(0, 18) + '...' : label
                }}
              />
              <Tooltip content={<CurrencyTooltip />} />
              <Bar dataKey="gross" name="Σύνολο" fill="#4f46e5" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* 7. Monthly Evolution (full width) */}
      <Card title="Μηνιαια Εξελιξη" full>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={monthEvo}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} />
            <Tooltip content={<CurrencyTooltip />} />
            <Legend />
            <Area
              type="monotone"
              dataKey="income"
              name="Έσοδα"
              stroke="#4f46e5"
              fill="#4f46e5"
              fillOpacity={0.15}
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="expenses"
              name="Έξοδα"
              stroke="#f43f5e"
              fill="#f43f5e"
              fillOpacity={0.1}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid gap-6 grid-cols-1 md:grid-cols-2">
        {/* 8. Average Invoice Value */}
        <Card title="Μεση Αξια Παραστατικου">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={avgInv}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <Tooltip content={<CurrencyTooltip />} />
              <Line type="monotone" dataKey="avg" name="Μ.Ο. Αξία" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* 9. Seasonality */}
        <Card title="Εποχικοτητα">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={seasonal}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <Tooltip content={<CurrencyTooltip />} />
              <Bar dataKey="avg_revenue" name="Μ.Ο. Εσόδων" fill="#818cf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* 10. Weekday Revenue */}
        <Card title="Ημερα Εβδομαδας">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={weekday}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} />
              <Tooltip content={<CurrencyTooltip />} />
              <Bar dataKey="avg_revenue" name="Μ.Ο. Εσόδων" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  )
}
