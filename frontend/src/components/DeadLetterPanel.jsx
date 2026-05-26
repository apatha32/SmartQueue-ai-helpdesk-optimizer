import { useEffect, useState } from 'react'
import { listDeadJobs, retryJob } from '../api/queue'
import { streamChat } from '../api/rag'

export default function DeadLetterPanel() {
  const [jobs,      setJobs]      = useState([])
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [retrying,  setRetrying]  = useState({})
  const [analysis,  setAnalysis]  = useState(null)
  const [analyzing, setAnalyzing] = useState(false)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      setJobs(await listDeadJobs() || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleRetry = async (id) => {
    setRetrying(r => ({ ...r, [id]: true }))
    try {
      await retryJob(id)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setRetrying(r => ({ ...r, [id]: false }))
    }
  }

  const analyzeWithAI = () => {
    if (!jobs.length || analyzing) return
    setAnalyzing(true)
    setAnalysis('')

    const summary = jobs
      .map(j => `• ${j.id.slice(0, 8)} [${j.type}] retries=${j.retries}/${j.max_retries} error="${j.error || 'none'}"`)
      .join('\n')

    const prompt =
      `Analyze these dead-letter queue jobs from a distributed task queue system. ` +
      `For each, identify the likely root cause and suggest a concrete fix:\n\n${summary}`

    streamChat(
      prompt,
      null,
      (chunk) => setAnalysis(prev => (prev || '') + chunk),
      ()      => setAnalyzing(false),
      (err)   => { setAnalysis(`Error: ${err}`); setAnalyzing(false) },
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Dead-Letter Queue</h2>
        <div className="dlq-actions">
          <button className="btn btn--secondary btn--sm" onClick={refresh} disabled={loading}>
            {loading ? '…' : 'Refresh'}
          </button>
          <button
            className="btn btn--accent btn--sm"
            onClick={analyzeWithAI}
            disabled={!jobs.length || analyzing}
          >
            {analyzing ? 'Analyzing…' : '✦ Analyze with AI'}
          </button>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {!loading && jobs.length === 0 && (
        <p className="text-muted empty-state">No dead-letter jobs — queue is healthy.</p>
      )}

      {jobs.length > 0 && (
        <div className="dlq-table">
          <div className="dlq-header">
            <span>Job ID</span>
            <span>Type</span>
            <span>Retries</span>
            <span>Error</span>
            <span />
          </div>
          {jobs.map(job => (
            <div key={job.id} className="dlq-row">
              <code className="dlq-id">{job.id.slice(0, 8)}…</code>
              <span className="dlq-type">{job.type}</span>
              <span>{job.retries}/{job.max_retries}</span>
              <span className="dlq-error">{job.error || '—'}</span>
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => handleRetry(job.id)}
                disabled={retrying[job.id]}
              >
                {retrying[job.id] ? '…' : 'Retry'}
              </button>
            </div>
          ))}
        </div>
      )}

      {(analysis || analyzing) && (
        <div className="ai-analysis card" style={{ marginTop: 16 }}>
          <h3 className="card-title">AI Analysis</h3>
          <div className="analysis-content">
            {analysis}
            {analyzing && <span className="cursor">▍</span>}
          </div>
        </div>
      )}
    </div>
  )
}
