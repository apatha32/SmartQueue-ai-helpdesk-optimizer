import { useState } from 'react'
import { getJob } from '../api/queue'

const PRIORITY_LABEL = ['', 'High', 'Medium', 'Low']

export default function JobList() {
  const [jobId,   setJobId]   = useState('')
  const [job,     setJob]     = useState(null)
  const [error,   setError]   = useState(null)
  const [loading, setLoading] = useState(false)

  const lookup = async (e) => {
    e.preventDefault()
    const id = jobId.trim()
    if (!id) return
    setLoading(true)
    setError(null)
    setJob(null)
    try {
      setJob(await getJob(id))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2 className="card-title">Job Lookup</h2>
      <form onSubmit={lookup} className="form">
        <div className="form-row">
          <label className="form-label">Job ID</label>
          <div className="input-row">
            <input
              className="input input--mono"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={jobId}
              onChange={e => setJobId(e.target.value)}
            />
            <button className="btn btn--secondary" type="submit" disabled={loading}>
              {loading ? '…' : 'Fetch'}
            </button>
          </div>
        </div>
      </form>

      {error && <p className="error-text">{error}</p>}

      {job && (
        <div className="job-detail">
          <div className="job-detail-row"><span>ID</span><code>{job.id}</code></div>
          <div className="job-detail-row"><span>Type</span><code>{job.type}</code></div>
          <div className="job-detail-row">
            <span>Status</span>
            <span className={`badge badge--${job.status}`}>{job.status}</span>
          </div>
          <div className="job-detail-row">
            <span>Priority</span>
            <span className={`badge badge--priority-${job.priority}`}>{PRIORITY_LABEL[job.priority]}</span>
          </div>
          <div className="job-detail-row"><span>Retries</span><code>{job.retries}/{job.max_retries}</code></div>
          {job.error && (
            <div className="job-detail-row">
              <span>Error</span><code className="error-text">{job.error}</code>
            </div>
          )}
          <div className="job-detail-row">
            <span>Created</span><code>{new Date(job.created_at).toLocaleString()}</code>
          </div>
          <div className="job-detail-row">
            <span>Payload</span>
            <pre className="payload-pre">{JSON.stringify(job.payload, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
