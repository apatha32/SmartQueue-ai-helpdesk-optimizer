import { useState, useEffect, useCallback } from "react";
import { getStats, listJobs, listDead, retryJob, getRecommendations, slaCheck } from "../api/index.js";

const P_COLOR = { 1: "#ef4444", 2: "#f59e0b", 3: "#3b82f6", 4: "#6b7280" };
const P_LABEL = { 1: "P1", 2: "P2", 3: "P3", 4: "P4" };
const URGENCY_COLOR = { critical: "#ef4444", high: "#f59e0b", medium: "#3b82f6", low: "#6b7280" };

export default function QueueHealth() {
  const [stats, setStats]             = useState(null);
  const [recs, setRecs]               = useState(null);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [slaRisks, setSlaRisks]       = useState([]);
  const [deadJobs, setDeadJobs]       = useState([]);
  const [retryingId, setRetryingId]   = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [s, jobs, dead] = await Promise.all([getStats(), listJobs(), listDead()]);
      setStats(s);
      setDeadJobs(Array.isArray(dead) ? dead : []);

      // SLA check
      if (Array.isArray(jobs) && jobs.length) {
        try {
          const sla = await slaCheck(jobs);
          setSlaRisks(sla.at_risk || []);
        } catch {}
      }
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const fetchRecs = async () => {
    if (!stats) return;
    setLoadingRecs(true);
    try {
      const r = await getRecommendations(stats);
      setRecs(r);
    } catch (e) {
      setRecs({ error: e.message });
    } finally {
      setLoadingRecs(false);
    }
  };

  const handleRetry = async id => {
    setRetryingId(id);
    try {
      await retryJob(id);
      refresh();
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div className="health-layout">
      {/* ── Stats row ──────────────────────────────────────── */}
      <div className="stats-row">
        {stats ? [
          { label: "Pending",    val: stats.pending_count,    cls: "pending"    },
          { label: "Processing", val: stats.processing_count, cls: "processing" },
          { label: "Completed",  val: stats.completed_count,  cls: "completed"  },
          { label: "Failed",     val: stats.failed_count,     cls: "failed"     },
          { label: "Dead",       val: stats.dead_count,       cls: "dead"       },
        ].map(({ label, val, cls }) => (
          <div key={label} className={`stat-card stat-${cls}`}>
            <div className="stat-val">{val ?? 0}</div>
            <div className="stat-label">{label}</div>
          </div>
        )) : <p className="loading-msg">Loading stats…</p>}
      </div>

      <div className="health-body">
        {/* ── SLA Risk ──────────────────────────────────────── */}
        <div className="card sla-card">
          <h2>SLA Risk</h2>
          {slaRisks.length === 0 ? (
            <p className="empty-msg">No at-risk tickets at this time.</p>
          ) : (
            <table className="sla-table">
              <thead>
                <tr>
                  <th>ID</th><th>Category</th><th>Priority</th>
                  <th>Risk</th><th>Remaining</th>
                </tr>
              </thead>
              <tbody>
                {slaRisks.map(r => (
                  <tr key={r.job_id}>
                    <td className="mono">{r.job_id.slice(0, 8)}</td>
                    <td>{r.category}</td>
                    <td>
                      <span className="badge" style={{ background: P_COLOR[r.priority] }}>
                        {P_LABEL[r.priority]}
                      </span>
                    </td>
                    <td>
                      <span className="risk-badge" style={{ color: riskColor(r.breach_risk) }}>
                        {r.breach_risk}
                      </span>
                    </td>
                    <td>{r.remaining_minutes < 0 ? "BREACHED" : `${r.remaining_minutes}m`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ── AI Recommendations ────────────────────────────── */}
        <div className="card recs-card">
          <div className="recs-header">
            <h2>AI Recommendations</h2>
            <button className="btn btn-primary" onClick={fetchRecs} disabled={loadingRecs}>
              {loadingRecs ? "Analysing..." : "Analyse Queue"}
            </button>
          </div>

          {!recs && !loadingRecs && (
            <p className="empty-msg">Click "Analyse Queue" to get AI workload recommendations.</p>
          )}
          {recs?.error && <p className="error-msg">Error: {recs.error}</p>}
          {recs && !recs.error && (
            <>
              <div className="health-score-row">
                <HealthGauge score={recs.health_score} />
                <p className="recs-summary">{recs.summary}</p>
              </div>
              <div className="rec-list">
                {(recs.recommendations || []).map((rec, i) => (
                  <div key={i} className="rec-item">
                    <div className="rec-top">
                      <span className="rec-action">{rec.action}</span>
                      <span
                        className="urgency-badge"
                        style={{ background: URGENCY_COLOR[rec.urgency] }}
                      >
                        {rec.urgency}
                      </span>
                    </div>
                    <p className="rec-detail">{rec.detail}</p>
                    {rec.affected_count > 0 && (
                      <p className="rec-affected">{rec.affected_count} ticket(s) affected</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* ── Dead Letter ───────────────────────────────────── */}
        {deadJobs.length > 0 && (
          <div className="card dead-card">
            <h2>Dead Letter Queue ({deadJobs.length})</h2>
            <div className="dead-list">
              {deadJobs.map(job => (
                <div key={job.id} className="dead-row">
                  <div className="dead-info">
                    <span className="mono">{job.id.slice(0, 8)}</span>
                    <span className="dead-error">{job.error?.slice(0, 80)}</span>
                  </div>
                  <button
                    className="btn btn-sm btn-warn"
                    disabled={retryingId === job.id}
                    onClick={() => handleRetry(job.id)}
                  >
                    {retryingId === job.id ? "…" : "Retry"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HealthGauge({ score }) {
  const color = score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="health-gauge" style={{ borderColor: color }}>
      <span className="gauge-num" style={{ color }}>{score}</span>
      <span className="gauge-label">/ 100</span>
    </div>
  );
}

function riskColor(risk) {
  switch (risk) {
    case "breached":  return "#ef4444";
    case "at_risk":   return "#f59e0b";
    case "warning":   return "#3b82f6";
    default:          return "#22c55e";
  }
}
