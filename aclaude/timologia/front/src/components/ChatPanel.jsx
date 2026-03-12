import { useState, useRef, useEffect } from 'react'
import { sseStream } from '../lib/api'
import ToolActivity from './ToolActivity'
import ConfirmationCard from './ConfirmationCard'

export default function ChatPanel({ companyId, sessionId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [activeTool, setActiveTool] = useState(null)
  const bottomRef = useRef(null)

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
    setMessages((prev) => [...prev, { role: 'assistant', content: '', confirmations: [] }])

    try {
      await sseStream(
        '/api/chat',
        { company_id: companyId, message: text, session_id: sessionId },
        (eventType, data) => {
          switch (eventType) {
            case 'text':
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  last.content += data.text || data.content || ''
                }
                return updated
              })
              setActiveTool(null)
              break

            case 'tool_call':
              setActiveTool(data)
              break

            case 'confirmation':
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  last.confirmations = [...(last.confirmations || []), data]
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

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-lg">Γεια! Πώς μπορώ να βοηθήσω;</p>
              <p className="mt-1 text-sm">Ρωτήστε για τιμολόγια, ΦΠΑ, αναφορές...</p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-slate-700'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>

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
      <form onSubmit={sendMessage} className="border-t border-gray-200 bg-white p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Γράψτε μήνυμα..."
            disabled={sending}
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-slate-700 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none disabled:bg-gray-50 disabled:opacity-60"
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
