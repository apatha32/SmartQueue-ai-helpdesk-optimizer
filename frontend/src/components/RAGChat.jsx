import { useEffect, useRef, useState } from 'react'
import { getEvaluation, ingestDocuments, streamChat } from '../api/rag'

const EVAL_METRICS = ['answer_relevancy', 'faithfulness', 'context_recall']

export default function RAGChat() {
  const [messages,    setMessages]    = useState([])
  const [input,       setInput]       = useState('')
  const [streaming,   setStreaming]   = useState(false)
  const [sessionId,   setSessionId]   = useState(null)
  const [evaluation,  setEvaluation]  = useState(null)
  const [showIngest,  setShowIngest]  = useState(false)
  const [ingestText,  setIngestText]  = useState('')
  const [ingestState, setIngestState] = useState(null)

  const abortRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = () => {
    const text = input.trim()
    if (!text || streaming) return

    setMessages(prev => [
      ...prev,
      { role: 'user',      content: text },
      { role: 'assistant', content: '', streaming: true },
    ])
    setInput('')
    setStreaming(true)
    setEvaluation(null)

    let resolvedSession = sessionId

    abortRef.current = streamChat(
      text,
      sessionId,
      (chunk, sid) => {
        if (sid && !resolvedSession) { resolvedSession = sid; setSessionId(sid) }
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          next[next.length - 1] = { ...last, content: last.content + chunk }
          return next
        })
      },
      async (sid) => {
        const finalSid = sid || resolvedSession
        if (finalSid) setSessionId(finalSid)
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = { ...next[next.length - 1], streaming: false }
          return next
        })
        setStreaming(false)
        if (finalSid) {
          // Poll for RAGAS evaluation (fires async in the backend ~3s after response)
          setTimeout(async () => {
            const ev = await getEvaluation(finalSid)
            if (ev && !ev.error) setEvaluation(ev)
          }, 4000)
        }
      },
      (err) => {
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = { role: 'error', content: err, streaming: false }
          return next
        })
        setStreaming(false)
      },
    )
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const handleIngest = async () => {
    if (!ingestText.trim()) return
    setIngestState('ingesting…')
    try {
      const res = await ingestDocuments([ingestText])
      setIngestState(`✓ Ingested ${res.ingested} document(s)`)
      setIngestText('')
    } catch (e) {
      setIngestState(`Error: ${e.message}`)
    }
  }

  return (
    <div className="rag-layout">
      <div className="rag-header">
        <h2 className="card-title">RAG Chat</h2>
        <div className="rag-meta">
          {sessionId && (
            <span className="session-badge">
              Session <code>{sessionId.slice(0, 8)}…</code>
            </span>
          )}
          <button className="btn btn--ghost btn--sm" onClick={() => setShowIngest(v => !v)}>
            {showIngest ? 'Hide Ingest' : '+ Ingest Document'}
          </button>
        </div>
      </div>

      {showIngest && (
        <div className="ingest-panel card">
          <h3 className="card-title">Add to Knowledge Base</h3>
          <p className="text-muted" style={{ marginBottom: 10 }}>
            Paste a document — it will be embedded, indexed in ChromaDB, and added to the BM25 corpus.
          </p>
          <textarea
            className="input input--mono"
            rows={5}
            placeholder="Paste document text here…"
            value={ingestText}
            onChange={e => setIngestText(e.target.value)}
          />
          <div className="ingest-actions">
            <button className="btn btn--primary" onClick={handleIngest}>Ingest</button>
            {ingestState && <span className="ingest-status">{ingestState}</span>}
          </div>
        </div>
      )}

      <div className="chat-window card">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything — the ReAct agent retrieves context via hybrid BM25 + dense search.</p>
            <p className="text-muted">Ingest a document above to populate the knowledge base.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message message--${msg.role}`}>
            <div className="message-role">
              {msg.role === 'user' ? 'You' : msg.role === 'error' ? '⚠ Error' : 'Agent'}
            </div>
            <div className="message-content">
              {msg.content}
              {msg.streaming && <span className="cursor">▍</span>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {evaluation && (
        <div className="eval-panel card">
          <div className="eval-title">RAGAS Evaluation</div>
          <div className="eval-metrics">
            {EVAL_METRICS.map(k => (
              <div key={k} className="eval-metric">
                <div className="eval-metric-info">
                  <span>{k.replace(/_/g, ' ')}</span>
                  <strong>{((evaluation[k] || 0) * 100).toFixed(1)}%</strong>
                </div>
                <div className="eval-metric-bar-wrap">
                  <div className="eval-metric-bar" style={{ width: `${(evaluation[k] || 0) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="chat-input-row">
        <textarea
          className="input chat-input"
          placeholder="Ask the agent… (Enter to send, Shift+Enter for newline)"
          rows={2}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <button
          className="btn btn--primary btn--send"
          onClick={send}
          disabled={streaming || !input.trim()}
        >
          {streaming ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
