import { useEffect, useState } from 'react'
import { getStats } from '../api/queue'

const STATS = [
  { key: 'pending_count',    label: 'Pending',    cls: 'accent'  },
  { key: 'processing_count', label: 'Processing', cls: 'warning' },
  { key: 'completed_count',  label: 'Completed',  cls: 'success' },
  { key: 'failed_count',     label: 'Failed',     cls: 'error'   },
  { key: 'dead_count',       label: 'Dead',       cls: 'muted'   },
]

export default function QueueStats() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const refresh = async () => {
      try {
        setStats(await getStats())
        setError(null)
      } catch (e) {
        setError(e.message)
      }
    }
    refresh()
    const id = setInterval(refresh, 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Queue Stats</h2>
        <span className="live-badge">● LIVE</span>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="stats-grid">
        {STATS.map(({ key, label, cls }) => (
          <div key={key} className={`stat-card stat-card--${cls}`}>
            <div className="stat-value">
              {stats ? stats[key].toLocaleString() : '—'}
            </div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
