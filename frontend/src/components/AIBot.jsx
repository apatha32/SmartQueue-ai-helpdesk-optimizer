import { useState, useEffect, useRef, useCallback } from "react";
import { listJobs, streamBot } from "../api/index.js";

const BOT_PLACEHOLDER = `Hello! I'm your AI support assistant powered by DeepSeek R1.

Select a ticket from the dropdown, or just ask me a general IT question.`;

export default function AIBot() {
  const [jobs, setJobs]           = useState([]);
  const [selectedJob, setSelected] = useState(null);
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId]               = useState(() => `session-${Date.now()}`);
  const bottomRef                 = useRef(null);
  const abortRef                  = useRef(null); // for future abort support

  // Load ticket list
  const refreshJobs = useCallback(async () => {
    try {
      const j = await listJobs();
      setJobs(Array.isArray(j) ? j : []);
    } catch {}
  }, []);

  useEffect(() => {
    refreshJobs();
    const id = setInterval(refreshJobs, 10000);
    return () => clearInterval(id);
  }, [refreshJobs]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Show placeholder welcome if no messages
  const showWelcome = messages.length === 0;

  const send = async () => {
    const msg = input.trim();
    if (!msg || streaming) return;
    setInput("");

    // Append user message
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setStreaming(true);

    // Append empty assistant message that we'll fill in
    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    const ticket = selectedJob
      ? {
          id:       selectedJob.id,
          type:     "support_ticket",
          priority: selectedJob.priority,
          payload:  selectedJob.payload || {},
        }
      : null;

    streamBot(
      msg,
      ticket,
      sessionId,
      chunk => {
        // Append chunk to last assistant message
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            ...copy[copy.length - 1],
            content: copy[copy.length - 1].content + chunk,
          };
          return copy;
        });
      },
      () => setStreaming(false),
      err => {
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            ...copy[copy.length - 1],
            content: `⚠ Error: ${err}`,
          };
          return copy;
        });
        setStreaming(false);
      },
    );
  };

  const handleKey = e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const clear = () => {
    setMessages([]);
    // Also clear server-side history (best effort)
    fetch("/api/ai/bot/clear", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ session_id: sessionId }),
    }).catch(() => {});
  };

  const jobOptions = jobs.filter(j => j.type === "support_ticket" || j.payload?.category);

  return (
    <div className="bot-layout">
      {/* ── Sidebar ────────────────────────────────────────── */}
      <div className="bot-sidebar card">
        <h2>AI Bot</h2>
        <p className="bot-sidebar-desc">
          Powered by <strong>DeepSeek R1</strong> via OpenRouter.<br />
          Ask anything or select a ticket for context.
        </p>

        <label className="field-label">Ticket context</label>
        <select
          className="select"
          value={selectedJob?.id || ""}
          onChange={e => {
            const job = jobs.find(j => j.id === e.target.value) || null;
            setSelected(job);
          }}
        >
          <option value="">— General (no ticket) —</option>
          {jobOptions.map(j => (
            <option key={j.id} value={j.id}>
              {j.payload?.summary?.slice(0, 40) || j.id.slice(0, 12)}
              {" · "}P{j.priority}
            </option>
          ))}
        </select>

        {selectedJob && (
          <div className="selected-ticket">
            <p className="field-label">Selected ticket</p>
            <p className="sel-summary">{selectedJob.payload?.summary || "—"}</p>
            <div className="sel-meta">
              <span>{selectedJob.payload?.category}</span>
              <span>{selectedJob.payload?.tier}</span>
              <span>P{selectedJob.priority}</span>
            </div>
          </div>
        )}

        <button className="btn btn-sm btn-ghost" onClick={clear}>Clear chat</button>
        <button className="btn btn-sm btn-ghost" onClick={refreshJobs}>Refresh tickets</button>
      </div>

      {/* ── Chat area ──────────────────────────────────────── */}
      <div className="bot-chat card">
        <div className="chat-messages">
          {showWelcome && (
            <div className="welcome-msg">
              <p>{BOT_PLACEHOLDER}</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              <div className="bubble-role">{m.role === "user" ? "You" : "AI Bot"}</div>
              <div className="bubble-content">{m.content || (m.role === "assistant" && streaming ? <span className="cursor">▌</span> : "")}</div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-row">
          <textarea
            className="chat-input"
            rows={2}
            placeholder="Ask the AI bot… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={streaming}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={send}
            disabled={!input.trim() || streaming}
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
