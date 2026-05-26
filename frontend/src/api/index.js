// Centralised API calls — all paths go through nginx proxy

const API = "/api/v1";
const AI  = "/api/ai";

// ── Queue / Ticket API ────────────────────────────────────────
export const getStats   = () => fetch(`${API}/stats`).then(r => r.json());
export const listJobs   = () => fetch(`${API}/jobs`).then(r => r.json());
export const listDead   = () => fetch(`${API}/jobs/dead`).then(r => r.json());
export const getJob     = id => fetch(`${API}/jobs/${id}`).then(r => r.json());
export const retryJob   = id => fetch(`${API}/jobs/${id}/retry`, { method: "POST" }).then(r => r.json());

export const submitJob  = body =>
  fetch(`${API}/jobs`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  }).then(r => r.json());

// ── AI Service API ────────────────────────────────────────────
export const classifyTicket = async (text, customer_tier = "standard") => {
  const r = await fetch(`${AI}/classify`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ text, customer_tier }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
  return body;
};

export const getRecommendations = async queue_stats => {
  const r = await fetch(`${AI}/recommend`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ queue_stats }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
  return body;
};

export const simulateTickets = (count, api_base = "http://api:8080") =>
  fetch(`${AI}/simulate`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ count, api_base }),
  }).then(r => r.json());

export const slaCheck = jobs =>
  fetch(`${AI}/sla-check`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ jobs }),
  }).then(r => r.json());

/**
 * Stream bot response via SSE.
 * @param {string}   message
 * @param {object}   ticket
 * @param {string}   sessionId
 * @param {function} onChunk   - called with each text chunk
 * @param {function} onDone    - called when stream ends
 * @param {function} onError   - called on error
 */
export function streamBot(message, ticket, sessionId, onChunk, onDone, onError) {
  fetch(`${AI}/bot/chat`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": sessionId,
    },
    body: JSON.stringify({ message, ticket, session_id: sessionId }),
  }).then(async res => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      onError(err.detail || "Request failed");
      return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") { onDone(); return; }
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) { onError(parsed.error); return; }
          if (parsed.chunk) onChunk(parsed.chunk);
        } catch { /* skip malformed line */ }
      }
    }
    onDone();
  }).catch(err => onError(err.message));
}
