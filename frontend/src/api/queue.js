const BASE = '/api/v1'

async function _fetch(path, opts = {}) {
  const r = await fetch(BASE + path, opts)
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { msg = (await r.json()).error || msg } catch {}
    throw new Error(msg)
  }
  return r.json()
}

export const getStats     = ()      => _fetch('/stats')
export const getJob       = (id)    => _fetch(`/jobs/${id}`)
export const listDeadJobs = ()      => _fetch('/jobs/dead')
export const retryJob     = (id)    => _fetch(`/jobs/${id}/retry`, { method: 'POST' })

export function submitJob(body) {
  return _fetch('/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
