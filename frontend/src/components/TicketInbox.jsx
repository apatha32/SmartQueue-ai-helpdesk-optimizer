import { useState, useEffect, useRef, useCallback } from "react";
import {
  classifyTicket, submitJob, listJobs, getStats, simulateTickets,
} from "../api/index.js";

const TIERS    = ["tier1", "tier2", "billing_team", "security_team", "engineering"];
const CATS     = ["all", "outage", "security", "billing", "technical", "access", "feature"];
const PRIORITY = { 1: "P1", 2: "P2", 3: "P3", 4: "P4" };
const P_COLOR  = { 1: "#ef4444", 2: "#f59e0b", 3: "#3b82f6", 4: "#6b7280" };

export default function TicketInbox() {
  const [text, setText]           = useState("");
  const [tier, setTier]           = useState("standard");
  const [classifying, setClassify] = useState(false);
  const [classified, setClassified] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted]   = useState(null);
  const [jobs, setJobs]             = useState([]);
  const [stats, setStats]           = useState(null);
  const [filter, setFilter]         = useState("all");
  const [simCount, setSimCount]     = useState(10);
  const [simRunning, setSimRunning] = useState(false);
  const [simMsg, setSimMsg]         = useState("");

  const refreshJobs = useCallback(async () => {
    try {
      const [j, s] = await Promise.all([listJobs(), getStats()]);
      setJobs(Array.isArray(j) ? j : []);
      setStats(s);
    } catch {}
  }, []);

  useEffect(() => {
    refreshJobs();
    const id = setInterval(refreshJobs, 3000);
    return () => clearInterval(id);
  }, [refreshJobs]);

  const handleClassify = async () => {
    if (!text.trim()) return;
    setClassify(true);
    setClassified(null);
    setSubmitted(null);
    try {
      const result = await classifyTicket(text, tier);
      setClassified(result);
    } catch (e) {
      setClassified({ error: e.message });
    } finally {
      setClassify(false);
    }
  };

  const handleSubmit = async () => {
    if (!classified || classified.error) return;
    setSubmitting(true);
    try {
      const job = await submitJob({
        type:        "support_ticket",
        priority:    classified.priority,
        max_retries: 3,
        payload: {
          text,
          customer_tier:     tier,
          category:          classified.category,
          tier:              classified.tier,
          estimated_minutes: classified.estimated_minutes,
          sla_hours:         classified.sla_hours,
          summary:           classified.summary,
          tags:              classified.tags || [],
        },
      });
      setSubmitted(job);
      setText("");
      setClassified(null);
      refreshJobs();
    } catch (e) {
      setSubmitted({ error: e.message });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSimulate = async () => {
    setSimRunning(true);
    setSimMsg("");
    try {
      const res = await simulateTickets(simCount);
      setSimMsg(`✓ ${res.submitted} tickets submitted`);
      refreshJobs();
    } catch (e) {
      setSimMsg(`✗ ${e.message}`);
    } finally {
      setSimRunning(false);
    }
  };

  const filtered = jobs.filter(j =>
    filter === "all" || j.payload?.category === filter
  );

  return (
    <div className="inbox-layout">
      {/* ── Left: Submit + Simulate ─────────────────────────── */}
      <div className="submit-panel card">
        <h2>New Ticket</h2>
        <label className="field-label">Customer tier</label>
        <select value={tier} onChange={e => setTier(e.target.value)} className="select">
          <option value="free">Free</option>
          <option value="standard">Standard</option>
          <option value="enterprise">Enterprise</option>
        </select>

        <label className="field-label">Describe the issue</label>
        <textarea
          className="textarea"
          rows={5}
          placeholder="e.g. Production API is down, users getting 500 errors…"
          value={text}
          onChange={e => setText(e.target.value)}
        />

        <button
          className="btn btn-primary"
          onClick={handleClassify}
          disabled={!text.trim() || classifying}
        >
          {classifying ? "Classifying…" : "AI Classify →"}
        </button>

        {classified && !classified.error && (
          <div className="classify-result">
            <div className="classify-row">
              <span className="badge" style={{ background: P_COLOR[classified.priority] }}>
                {PRIORITY[classified.priority]}
              </span>
              <span className="badge badge-cat">{classified.category}</span>
              <span className="badge badge-tier">{classified.tier}</span>
            </div>
            <p className="classify-summary">{classified.summary}</p>
            <div className="classify-meta">
              <span>SLA: {classified.sla_hours}h</span>
              <span>Est: {classified.estimated_minutes}min</span>
            </div>
            {classified.tags?.length > 0 && (
              <div className="tags-row">
                {classified.tags.map(t => <span key={t} className="tag">{t}</span>)}
              </div>
            )}
            <button
              className="btn btn-success"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? "Submitting…" : "Submit to Queue ↗"}
            </button>
          </div>
        )}
        {classified?.error && <p className="error-msg">Error: {classified.error}</p>}
        {submitted && !submitted.error && (
          <p className="success-msg">✓ Ticket queued — ID: {submitted.id?.slice(0, 8)}</p>
        )}

        {/* Simulator */}
        <div className="sim-box">
          <h3>Demo Flood</h3>
          <div className="sim-row">
            <input
              type="number" min={1} max={50}
              value={simCount}
              onChange={e => setSimCount(Number(e.target.value))}
              className="sim-input"
            />
            <button className="btn btn-warn" onClick={handleSimulate} disabled={simRunning}>
              {simRunning ? "Flooding…" : `Simulate ${simCount} Tickets`}
            </button>
          </div>
          {simMsg && <p className="sim-msg">{simMsg}</p>}
        </div>
      </div>

      {/* ── Right: Live queue ──────────────────────────────── */}
      <div className="queue-panel card">
        <div className="queue-header">
          <h2>Live Queue</h2>
          {stats && (
            <div className="mini-stats">
              <span className="stat-chip pending">{stats.pending_count} pending</span>
              <span className="stat-chip processing">{stats.processing_count} processing</span>
              <span className="stat-chip dead">{stats.dead_count} dead</span>
            </div>
          )}
        </div>

        <div className="filter-bar">
          {CATS.map(c => (
            <button
              key={c}
              className={`filter-btn ${filter === c ? "active" : ""}`}
              onClick={() => setFilter(c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="ticket-list">
          {filtered.length === 0 && (
            <p className="empty-msg">No tickets yet — submit one or run a demo flood.</p>
          )}
          {filtered.map(job => (
            <TicketRow key={job.id} job={job} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TicketRow({ job }) {
  const p = job.payload || {};
  const pri = job.priority || 3;
  return (
    <div className="ticket-row">
      <div className="ticket-left">
        <span className="badge" style={{ background: P_COLOR[pri], minWidth: 32 }}>
          {PRIORITY[pri]}
        </span>
        <div>
          <p className="ticket-summary">{p.summary || p.text?.slice(0, 60) || job.id.slice(0,8)}</p>
          <p className="ticket-meta">
            {p.category} · {p.tier} · SLA {p.sla_hours}h
          </p>
        </div>
      </div>
      <span className={`status-badge ${job.status}`}>{job.status}</span>
    </div>
  );
}
