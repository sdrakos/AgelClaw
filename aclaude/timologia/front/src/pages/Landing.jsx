import { useNavigate } from 'react-router-dom'
import { isAuthenticated } from '../lib/auth'
import { useEffect } from 'react'

export default function Landing() {
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated()) navigate('/app')
  }, [navigate])

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="mx-auto max-w-6xl flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <span className="text-lg font-bold text-white">T</span>
            </div>
            <span className="text-xl font-bold text-slate-800">Timologia</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-gray-50 transition-colors"
            >
              Σύνδεση
            </button>
            <button
              onClick={() => navigate('/login')}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors shadow-sm"
            >
              Δωρεάν Εγγραφή
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden pt-32 pb-20 lg:pt-40 lg:pb-28">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-50 via-white to-purple-50" />
        <div className="absolute top-20 left-1/4 h-72 w-72 rounded-full bg-indigo-200/30 blur-3xl" />
        <div className="absolute bottom-10 right-1/4 h-96 w-96 rounded-full bg-purple-200/20 blur-3xl" />

        <div className="relative mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-4 py-1.5 text-sm font-medium text-indigo-600">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
              Συνδεδεμένο με ΑΑΔΕ myDATA
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
              Ηλεκτρονική Τιμολόγηση
              <span className="block mt-2 bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                Απλά & Έξυπνα
              </span>
            </h1>
            <p className="mt-6 text-lg text-slate-600 leading-relaxed sm:text-xl">
              Διαχειριστείτε τα παραστατικά σας, παρακολουθήστε τα οικονομικά σας
              και αξιοποιήστε την τεχνητή νοημοσύνη — όλα σε ένα μέρος.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => navigate('/login')}
                className="w-full sm:w-auto rounded-xl bg-indigo-600 px-8 py-3.5 text-base font-semibold text-white hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-500/25 hover:shadow-xl hover:shadow-indigo-500/30"
              >
                Ξεκινήστε Δωρεάν
              </button>
              <a
                href="#features"
                className="w-full sm:w-auto rounded-xl border border-gray-200 bg-white px-8 py-3.5 text-base font-semibold text-slate-700 hover:bg-gray-50 hover:border-gray-300 transition-all text-center"
              >
                Μάθετε Περισσότερα
              </a>
            </div>
          </div>

          {/* Hero visual — app mockup */}
          <div className="mt-16 mx-auto max-w-4xl">
            <div className="rounded-2xl bg-gradient-to-b from-slate-800 to-slate-900 p-2 shadow-2xl shadow-slate-900/30 ring-1 ring-white/10">
              <div className="rounded-xl bg-slate-900 overflow-hidden">
                {/* Browser chrome */}
                <div className="flex items-center gap-2 px-4 py-3 bg-slate-800/50 border-b border-white/5">
                  <div className="flex gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-red-400/60" />
                    <div className="h-2.5 w-2.5 rounded-full bg-yellow-400/60" />
                    <div className="h-2.5 w-2.5 rounded-full bg-green-400/60" />
                  </div>
                  <div className="flex-1 flex justify-center">
                    <div className="rounded-md bg-slate-700/50 px-4 py-1 text-xs text-slate-400">timologia.me</div>
                  </div>
                </div>
                {/* Dashboard preview */}
                <div className="p-6 bg-gray-50">
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    {[
                      { label: 'Μηνιαίος Τζίρος', value: '12.480,00 €', color: 'bg-indigo-500' },
                      { label: 'ΦΠΑ Μήνα', value: '2.995,20 €', color: 'bg-emerald-500' },
                      { label: 'Παραστατικά', value: '47', color: 'bg-amber-500' },
                    ].map((c) => (
                      <div key={c.label} className="rounded-lg bg-white p-3 shadow-sm">
                        <div className="flex items-center gap-2">
                          <div className={`h-7 w-7 rounded-md ${c.color} flex items-center justify-center`}>
                            <div className="h-3 w-3 rounded-full bg-white/30" />
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-400">{c.label}</p>
                            <p className="text-sm font-semibold text-slate-700">{c.value}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Mini chart bars */}
                  <div className="rounded-lg bg-white p-4 shadow-sm">
                    <p className="text-xs font-medium text-slate-500 mb-3">Μηνιαία Εξέλιξη</p>
                    <div className="flex items-end gap-1.5 h-20">
                      {[35, 45, 55, 40, 65, 80, 70, 90, 85, 95, 75, 100].map((h, i) => (
                        <div key={i} className="flex-1 flex flex-col gap-0.5">
                          <div className="rounded-sm bg-indigo-500/80" style={{ height: `${h}%` }} />
                          <div className="rounded-sm bg-orange-400/60" style={{ height: `${h * 0.4}%` }} />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 lg:py-28 bg-white">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 sm:text-4xl">
              Όλα όσα χρειάζεστε, σε μία πλατφόρμα
            </h2>
            <p className="mt-4 text-lg text-slate-500">
              Από την έκδοση παραστατικών μέχρι αναφορές και AI chat — το Timologia καλύπτει κάθε ανάγκη.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="group rounded-2xl border border-gray-100 bg-white p-7 hover:border-indigo-100 hover:shadow-lg hover:shadow-indigo-500/5 transition-all">
                <div className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl ${f.bg}`}>
                  <f.icon />
                </div>
                <h3 className="text-lg font-semibold text-slate-800 mb-2">{f.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 lg:py-28 bg-gradient-to-b from-gray-50 to-white">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 sm:text-4xl">
              3 Βήματα για να Ξεκινήσετε
            </h2>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s.title} className="relative text-center">
                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-xl font-bold text-white shadow-lg shadow-indigo-500/30">
                  {i + 1}
                </div>
                <h3 className="text-lg font-semibold text-slate-800 mb-2">{s.title}</h3>
                <p className="text-sm text-slate-500">{s.desc}</p>
                {i < 2 && (
                  <div className="hidden md:block absolute top-7 left-[60%] w-[80%] border-t-2 border-dashed border-indigo-200" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-16 bg-gradient-to-r from-indigo-600 to-purple-600">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4 text-center">
            {STATS.map((s) => (
              <div key={s.label}>
                <p className="text-3xl font-bold text-white">{s.value}</p>
                <p className="mt-1 text-sm text-indigo-200">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* AI Section */}
      <section className="py-20 lg:py-28 bg-white">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid gap-12 lg:grid-cols-2 items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-purple-50 px-4 py-1.5 text-sm font-medium text-purple-600 mb-6">
                <SparklesIcon />
                AI Assistant
              </div>
              <h2 className="text-3xl font-bold text-slate-900 sm:text-4xl">
                Ρωτήστε ό,τι θέλετε στα Ελληνικά
              </h2>
              <p className="mt-4 text-lg text-slate-500 leading-relaxed">
                Ο AI βοηθός κατανοεί τα πάντα: εκδώστε τιμολόγια, ζητήστε αναφορές,
                δείτε στατιστικά — απλά γράψτε τι θέλετε.
              </p>
              <ul className="mt-8 space-y-4">
                {AI_FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-3">
                    <div className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100">
                      <CheckIcon />
                    </div>
                    <span className="text-sm text-slate-600">{f}</span>
                  </li>
                ))}
              </ul>
            </div>
            {/* Chat mockup */}
            <div className="rounded-2xl bg-slate-50 border border-gray-200 p-6 shadow-sm">
              <div className="space-y-4">
                <ChatBubble role="user" text="Πόσα έσοδα είχα τον Φεβρουάριο;" />
                <ChatBubble role="ai" text="Τον Φεβρουάριο 2026 εκδόσατε 38 παραστατικά με συνολικά έσοδα 11.693,40 €. Ο μέσος όρος ανά τιμολόγιο ήταν 307,72 €." />
                <ChatBubble role="user" text="Στείλε μου αναφορά εσόδων στο email" />
                <ChatBubble role="ai" text="Δημιούργησα την αναφορά εσόδων Φεβρουαρίου (Excel) και τη στέλνω στο email σας." />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Security */}
      <section className="py-20 lg:py-28 bg-gray-50">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 sm:text-4xl">
              Ασφάλεια Πρώτα
            </h2>
            <p className="mt-4 text-lg text-slate-500">
              Τα δεδομένα σας προστατεύονται με τα υψηλότερα πρότυπα ασφαλείας.
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {SECURITY.map((s) => (
              <div key={s.title} className="flex items-start gap-4 rounded-xl bg-white p-6 shadow-sm border border-gray-100">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50">
                  <s.icon />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-800">{s.title}</h4>
                  <p className="mt-1 text-sm text-slate-500">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 lg:py-28 bg-white">
        <div className="mx-auto max-w-3xl text-center px-6">
          <h2 className="text-3xl font-bold text-slate-900 sm:text-4xl">
            Ξεκινήστε σήμερα — δωρεάν
          </h2>
          <p className="mt-4 text-lg text-slate-500">
            Δημιουργήστε λογαριασμό σε λίγα δευτερόλεπτα και συνδέστε την επιχείρησή σας με το ΑΑΔΕ myDATA.
          </p>
          <button
            onClick={() => navigate('/login')}
            className="mt-8 rounded-xl bg-indigo-600 px-10 py-4 text-base font-semibold text-white hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-500/25 hover:shadow-xl hover:shadow-indigo-500/30"
          >
            Δημιουργία Λογαριασμού
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 bg-gray-50 py-10">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <span className="text-sm font-bold text-white">T</span>
              </div>
              <span className="text-lg font-bold text-slate-700">Timologia</span>
            </div>
            <p className="text-sm text-slate-400">
              Powered by <span className="font-semibold text-slate-500">Agel AI</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ── Data ── */

const FEATURES = [
  {
    title: 'Σύνδεση ΑΑΔΕ myDATA',
    desc: 'Αυτόματη λήψη εκδοθέντων και ληφθέντων παραστατικών απευθείας από την ΑΑΔΕ.',
    bg: 'bg-indigo-100 text-indigo-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
      </svg>
    ),
  },
  {
    title: 'Αναλυτικά Στατιστικά',
    desc: 'Γραφήματα εσόδων-εξόδων, ΦΠΑ, εποχικότητα, top πελάτες & προμηθευτές.',
    bg: 'bg-emerald-100 text-emerald-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3v18h18M7 16l4-4 4 4 5-5" />
      </svg>
    ),
  },
  {
    title: 'AI Chat Βοηθός',
    desc: 'Ρωτήστε στα Ελληνικά για τα οικονομικά σας, εκδώστε τιμολόγια ή ζητήστε αναφορές.',
    bg: 'bg-purple-100 text-purple-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    title: 'Αναφορές & Excel',
    desc: '5 preset αναφορές, εξαγωγή Excel, αυτόματη αποστολή στο email σας.',
    bg: 'bg-amber-100 text-amber-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    title: 'Multi-User & Ρόλοι',
    desc: 'Προσκαλέστε λογιστές και συνεργάτες με δικαιώματα owner, accountant ή viewer.',
    bg: 'bg-sky-100 text-sky-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
  },
  {
    title: 'Πολλαπλές Εταιρείες',
    desc: 'Διαχειριστείτε πολλές εταιρείες από ένα λογαριασμό — ιδανικό για λογιστές.',
    bg: 'bg-rose-100 text-rose-600',
    icon: () => (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
]

const STEPS = [
  {
    title: 'Δημιουργήστε Λογαριασμό',
    desc: 'Εγγραφείτε δωρεάν με email σε λίγα δευτερόλεπτα.',
  },
  {
    title: 'Συνδέστε την ΑΑΔΕ',
    desc: 'Εισάγετε τα κλειδιά myDATA και συγχρονίστε τα παραστατικά σας.',
  },
  {
    title: 'Ξεκινήστε',
    desc: 'Δείτε στατιστικά, ζητήστε αναφορές ή μιλήστε με τον AI βοηθό.',
  },
]

const STATS = [
  { value: '100%', label: 'Συμβατό με myDATA' },
  { value: '24/7', label: 'Διαθεσιμότητα' },
  { value: 'AI', label: 'Τεχνητή Νοημοσύνη' },
  { value: '256-bit', label: 'Κρυπτογράφηση' },
]

const AI_FEATURES = [
  '"Πόσα έσοδα είχα τον τελευταίο μήνα;"',
  '"Έκδωσε τιμολόγιο 500€ στην εταιρεία Χ"',
  '"Στείλε μου αναφορά ΦΠΑ στο email"',
  '"Ποιοι είναι οι top 5 πελάτες μου;"',
]

const SECURITY = [
  {
    title: 'Κρυπτογράφηση Fernet',
    desc: 'Τα AADE credentials αποθηκεύονται κρυπτογραφημένα με AES-128.',
    icon: () => (
      <svg className="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
    ),
  },
  {
    title: 'JWT Authentication',
    desc: 'Ασφαλής αυθεντικοποίηση με tokens και bcrypt hashing.',
    icon: () => (
      <svg className="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    title: 'Role-Based Access',
    desc: 'Κάθε χρήστης βλέπει μόνο τις εταιρείες στις οποίες έχει πρόσβαση.',
    icon: () => (
      <svg className="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
      </svg>
    ),
  },
]

/* ── Components ── */

function ChatBubble({ role, text }) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-indigo-600 text-white rounded-br-md'
          : 'bg-white text-slate-700 shadow-sm border border-gray-100 rounded-bl-md'
      }`}>
        {text}
      </div>
    </div>
  )
}

function SparklesIcon() {
  return (
    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="h-3 w-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  )
}
