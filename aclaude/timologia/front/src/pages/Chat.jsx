import { useState, useEffect, useRef } from 'react'
import { apiJson } from '../lib/api'
import { useCompany } from '../context/CompanyContext'
import ChatPanel from '../components/ChatPanel'

export default function Chat() {
  const { activeCompanyId } = useCompany()
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [loadingSessions, setLoadingSessions] = useState(false)
  const defaultSessionRef = useRef(null)

  useEffect(() => {
    if (!activeCompanyId) return
    setLoadingSessions(true)
    apiJson(`/api/chat/sessions?company_id=${activeCompanyId}`)
      .then((data) => {
        const list = data.items || data.sessions || data || []
        setSessions(list)
        if (!activeSession && list.length > 0) {
          setActiveSession(list[0].id)
        }
      })
      .catch(() => setSessions([]))
      .finally(() => setLoadingSessions(false))
  }, [activeCompanyId])

  const createSession = () => {
    const id = `session_${Date.now()}`
    setActiveSession(id)
    setSessions((prev) => [{ id, title: 'Νέα Συζήτηση', created_at: new Date().toISOString() }, ...prev])
    setSidebarOpen(false)
  }

  if (!activeCompanyId) {
    return (
      <div className="flex h-[calc(100vh-8rem)] items-center justify-center text-gray-400">
        Επιλέξτε εταιρεία για να συνεχίσετε
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Session sidebar toggle (mobile) */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="fixed bottom-20 right-4 z-20 rounded-full bg-indigo-600 p-3 text-white shadow-lg hover:bg-indigo-700 lg:hidden"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16m-7 6h7" />
        </svg>
      </button>

      {/* Session sidebar */}
      <div
        className={`${
          sidebarOpen ? 'fixed inset-0 z-30 bg-black/40 lg:relative lg:bg-transparent' : ''
        } lg:block`}
        onClick={(e) => {
          if (e.target === e.currentTarget) setSidebarOpen(false)
        }}
      >
        <div
          className={`${
            sidebarOpen ? 'fixed left-0 top-0 z-40 h-full' : 'hidden'
          } w-64 rounded-lg bg-white shadow-sm lg:relative lg:block`}
        >
          <div className="flex items-center justify-between border-b border-gray-100 p-3">
            <h3 className="text-sm font-semibold text-slate-700">Συζητήσεις</h3>
            <button
              onClick={createSession}
              className="rounded-md bg-indigo-600 p-1.5 text-white hover:bg-indigo-700 transition-colors"
              title="Νέα συζήτηση"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>

          <div className="overflow-y-auto p-2" style={{ maxHeight: 'calc(100vh - 12rem)' }}>
            {loadingSessions ? (
              <p className="p-3 text-sm text-gray-400">Φόρτωση...</p>
            ) : sessions.length === 0 ? (
              <p className="p-3 text-sm text-gray-400">Καμία συζήτηση</p>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setActiveSession(s.id)
                    setSidebarOpen(false)
                  }}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                    activeSession === s.id
                      ? 'bg-indigo-50 text-indigo-700 font-medium'
                      : 'text-slate-600 hover:bg-gray-50'
                  }`}
                >
                  <p className="truncate">{s.last_message || s.title || 'Συζήτηση'}</p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {s.message_count ? `${s.message_count} μηνύματα · ` : ''}
                    {s.updated_at
                      ? new Date(s.updated_at).toLocaleDateString('el-GR')
                      : s.created_at
                        ? new Date(s.created_at).toLocaleDateString('el-GR')
                        : ''}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Chat panel */}
      <div className="flex-1 rounded-lg bg-white shadow-sm overflow-hidden">
        <ChatPanel
          companyId={activeCompanyId}
          sessionId={activeSession || (() => {
            if (!defaultSessionRef.current) defaultSessionRef.current = `new_${Date.now()}`
            return defaultSessionRef.current
          })()}
        />
      </div>
    </div>
  )
}
