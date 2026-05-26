const BASE = '/api/rag'

/**
 * Stream a chat message via SSE (POST + ReadableStream).
 * Returns an AbortController so the caller can cancel mid-stream.
 *
 * @param {string}   message
 * @param {string|null} sessionId
 * @param {(chunk: string, sessionId: string) => void} onChunk
 * @param {(sessionId: string) => void} onDone
 * @param {(error: string) => void} onError
 */
export function streamChat(message, sessionId, onChunk, onDone, onError) {
  const ctrl = new AbortController()

  fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try { msg = (await res.json()).detail || msg } catch {}
        onError(msg)
        return
      }

      // Grab session_id from response header if present
      let activeSession = sessionId || res.headers.get('X-Session-ID') || null

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = 'message'

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.session_id) activeSession = data.session_id
              if (currentEvent === 'message' && data.chunk) {
                onChunk(data.chunk, activeSession)
              } else if (currentEvent === 'done') {
                onDone(activeSession)
              }
            } catch {}
            currentEvent = 'message' // reset after data line
          }
        }
      }

      onDone(activeSession)
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err.message)
    })

  return ctrl
}

export async function ingestDocuments(documents, metadata = []) {
  const r = await fetch(`${BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ documents, metadata }),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

export async function getEvaluation(sessionId) {
  const r = await fetch(`${BASE}/evaluate/${sessionId}`)
  if (!r.ok) return null
  return r.json()
}
