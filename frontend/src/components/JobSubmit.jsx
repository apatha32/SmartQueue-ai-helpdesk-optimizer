import { useState } from 'react'
import { submitJob } from '../api/queue'

const JOB_TYPES = ['email', 'image_resize', 'report', 'ai_agent']

const DEFAULT_PAYLOADS = {
  email:        '{\n  "to": "user@example.com",\n  "subject": "Hello"\n}',
  image_resize: '{\n  "url": "https://example.com/img.jpg",\n  "width": 800\n}',
  report:       '{\n  "report_id": "Q1-2026",\n  "format": "pdf"\n}',
  ai_agent:     '{\n  "task": "Summarize the key advantages of distributed task queues"\n}',
}

const PRIORITY_LABEL = ['', 'High', 'Medium', 'Low']

export default function JobSubmit() {
  const [type,       setType]       = useState('ai_agent')
  const [payload,    setPayload]    = useState(DEFAULT_PAYLOADS.ai_agent)
  const [priority,   setPriority]   = useState(2)
  const [maxRetries, setMaxRetries] = useState(3)
  const [result,     setResult]     = useState(null)
  const [error,      setError]      = useState(null)
  const [loading,    setLoading]    = useState(false)

  const handleTypeChange = (t) => {
    setType(t)
    setPayload(DEFAULT_PAYLOADS[t] || '{}')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let parsed
      try { parsed = JSON.parse(payload) } catch { throw new Error('Invalid JSON in payload') }
      const job = await submitJob({ type, payload: parsed, priority, max_retries: maxRetries })
      setResult(job)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2 className="card-title">Submit Job</h2>
      <form onSubmit={handleSubmit} className="form">
        <div className="form-row">
          <label className="form-label">Type</label>
          <select className="input" value={type} onChange={e => handleTypeChange(e.target.value)}>
            {JOB_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="form-row">
          <label className="form-label">Payload (JSON)</label>
          <textarea
            className="input input--mono"
            rows={5}
            value={payload}
            onChange={e => setPayload(e.target.value)}
          />
        </div>

        <div className="form-row-inline">
          <div className="form-row">
            <label className="form-label">Priority</label>
            <select className="input" value={priority} onChange={e => setPriority(Number(e.target.value))}>
              <option value={1}>High</option>
              <option value={2}>Medium</option>
              <option value={3}>Low</option>
            </select>
          </div>
          <div className="form-row">
            <label className="form-label">Max Retries</label>
            <input
              className="input"
              type="number"
              min={0} max={10}
              value={maxRetries}
              onChange={e => setMaxRetries(Number(e.target.value))}
            />
          </div>
        </div>

        <button className="btn btn--primary" type="submit" disabled={loading}>
          {loading ? 'Submitting…' : 'Submit Job'}
        </button>
      </form>

      {error  && <p className="error-text">{error}</p>}

      {result && (
        <div className="result-block">
          <div className="result-row">
            <span className="result-label">ID</span>
            <code className="result-value">{result.id}</code>
          </div>
          <div className="result-row">
            <span className="result-label">Status</span>
            <span className={`badge badge--${result.status}`}>{result.status}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Priority</span>
            <span className={`badge badge--priority-${result.priority}`}>{PRIORITY_LABEL[result.priority]}</span>
          </div>
        </div>
      )}
    </div>
  )
}
