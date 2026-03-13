import { useState, useRef, useEffect } from 'react'
import { sseStream, apiJson } from '../lib/api'
import ToolActivity from './ToolActivity'
import ConfirmationCard from './ConfirmationCard'

export default function ChatPanel({ companyId, sessionId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTool, setActiveTool] = useState(null)
  const bottomRef = useRef(null)
  const realSessionId = useRef(sessionId)

  useEffect(() => {
    realSessionId.current = sessionId
    setMessages([])
    setError('')

    // Load history for existing sessions (integer IDs from DB)
    if (sessionId && typeof sessionId === 'number') {
      setLoading(true)
      apiJson(`/api/chat/sessions/${sessionId}/messages`)
        .then((data) => {
          const msgs = (data.messages || []).map((m) => ({
            role: m.role,
            content: m.content,
            confirmations: [],
          }))
          setMessages(msgs)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeTool])

  const sendMessage = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return

    setInput('')
    setSending(true)
    setError('')
    setActiveTool(null)

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: text }])

    // Prepare assistant message slot
    const assistantIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '', confirmations: [], files: [] }])

    try {
      await sseStream(
        '/api/chat',
        { company_id: companyId, message: text, session_id: realSessionId.current },
        (eventType, data) => {
          console.log('[SSE EVENT]', eventType, JSON.stringify(data).slice(0, 200))
          switch (eventType) {
            case 'text':
              if (data.session_id) realSessionId.current = data.session_id
              setMessages((prev) => {
                const updated = [...prev]
                const lastIdx = updated.length - 1
                const last = updated[lastIdx]
                if (last && last.role === 'assistant') {
                  console.log('[TEXT EVENT] files preserved:', last.files?.length, last.files)
                  updated[lastIdx] = {
                    ...last,
                    content: last.content + (data.text || data.content || ''),
                  }
                }
                return updated
              })
              setActiveTool(null)
              break

            case 'tool_call':
              setActiveTool(data)
              break

            case 'file':
              console.log('[FILE EVENT] received:', data)
              setMessages((prev) => {
                const updated = [...prev]
                const lastIdx = updated.length - 1
                const last = updated[lastIdx]
                console.log('[FILE EVENT] last msg:', last?.role, 'files before:', last?.files?.length)
                if (last && last.role === 'assistant') {
                  updated[lastIdx] = {
                    ...last,
                    files: [...(last.files || []), data],
                  }
                  console.log('[FILE EVENT] files after:', updated[lastIdx].files.length)
                }
                return updated
              })
              setActiveTool(null)
              break

            case 'confirmation':
              setMessages((prev) => {
                const updated = [...prev]
                const lastIdx = updated.length - 1
                const last = updated[lastIdx]
                if (last && last.role === 'assistant') {
                  updated[lastIdx] = {
                    ...last,
                    confirmations: [...(last.confirmations || []), data],
                  }
                }
                return updated
              })
              setActiveTool(null)
              break

            case 'error':
              setError(data.message || data.error || 'Σφάλμα')
              setActiveTool(null)
              break

            case 'done':
              setActiveTool(null)
              setSending(false)
              break
          }
        }
      )
    } catch (err) {
      setError('Σφάλμα σύνδεσης. Δοκιμάστε ξανά.')
    } finally {
      setSending(false)
      setActiveTool(null)
    }
  }

  const handleConfirmResult = (action, data) => {
    if (data.message) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.message, confirmations: [] },
      ])
    }
  }

  const handleDownload = async (file) => {
    const token = localStorage.getItem('token')
    try {
      const res = await fetch(file.download_url, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Download failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('Σφάλμα λήψης αρχείου')
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3">
        {loading && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <svg className="mr-2 h-5 w-5 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Φόρτωση ιστορικού...
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-lg">Γεια! Πώς μπορώ να βοηθήσω;</p>
              <p className="mt-1 text-sm">Ρωτήστε για παραστατικά, ΦΠΑ, αναφορές...</p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] sm:max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-slate-700'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {/* Thinking indicator for empty assistant messages */}
                {msg.role === 'assistant' && !msg.content && sending && i === messages.length - 1 && (
                  <div className="flex items-center gap-1.5 py-1">
                    <span className="h-2 w-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="h-2 w-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="h-2 w-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                )}
              </div>
            </div>

            {/* File downloads */}
            {msg.files?.map((file, fi) => (
              <div key={fi} className="mt-2 ml-2">
                <button
                  onClick={() => handleDownload(file)}
                  className="inline-flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 hover:bg-green-100 transition-colors"
                >
                  <svg className="h-8 w-8 flex-shrink-0" viewBox="0 0 32 32" fill="none">
                    <rect x="4" y="2" width="24" height="28" rx="2" fill="#21A366" />
                    <path d="M8 8h6v4H8V8zm0 6h6v4H8v-4zm0 6h6v4H8v-4zm8-12h8v4h-8V8zm0 6h8v4h-8v-4zm0 6h8v4h-8v-4z" fill="#fff" opacity="0.9" />
                    <text x="10" y="20" fill="#fff" fontSize="7" fontWeight="bold" fontFamily="Arial">XLS</text>
                  </svg>
                  <div className="text-left">
                    <p className="font-medium">{file.filename}</p>
                    <p className="text-xs text-green-600">Κάντε κλικ για λήψη</p>
                  </div>
                  <svg className="h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                </button>
              </div>
            ))}

            {/* Confirmations */}
            {msg.confirmations?.map((conf, ci) => (
              <div key={ci} className="mt-2 ml-2">
                <ConfirmationCard confirmation={conf} onResult={handleConfirmResult} />
              </div>
            ))}
          </div>
        ))}

        {activeTool && (
          <div className="ml-2">
            <ToolActivity tool={activeTool} />
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={sendMessage} className="border-t border-gray-200 bg-white p-3 sm:p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Γράψτε μήνυμα..."
            disabled={sending}
            className="flex-1 rounded-lg border border-gray-300 px-3 sm:px-4 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none disabled:bg-gray-50 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? (
              <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
