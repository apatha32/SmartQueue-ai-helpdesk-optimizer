import { useState, useEffect } from 'react'
import TicketInbox from './components/TicketInbox'
import QueueHealth from './components/QueueHealth'
import AIBot from './components/AIBot'
import './App.css'

function Splash({ onDone }) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const show  = setTimeout(() => setLeaving(true), 1200)
    const clear = setTimeout(() => onDone(), 2000)
    return () => { clearTimeout(show); clearTimeout(clear) }
  }, [onDone])

  return (
    <div className={`splash${leaving ? ' splash--up' : ''}`}>
      <div className="splash-inner">
        <div className="splash-logo">
          <svg width="36" height="36" viewBox="0 0 16 16" fill="none">
            <rect x="2" y="2" width="5" height="5" rx="1" fill="white"/>
            <rect x="9" y="2" width="5" height="5" rx="1" fill="white" opacity=".7"/>
            <rect x="2" y="9" width="5" height="5" rx="1" fill="white" opacity=".7"/>
            <rect x="9" y="9" width="5" height="5" rx="1" fill="white" opacity=".4"/>
          </svg>
        </div>
        <h1 className="splash-title">SmartQueue</h1>
        <p className="splash-sub">AI Helpdesk Workload Optimizer</p>
      </div>
    </div>
  )
}

const TABS = [
  { id: 'inbox',  label: 'Ticket Inbox' },
  { id: 'health', label: 'Queue Health' },
  { id: 'bot',    label: 'AI Assistant' },
]

export default function App() {
  const [active, setActive]   = useState('inbox')
  const [splashDone, setSplash] = useState(false)

  return (
    <div className="app">
      {!splashDone && <Splash onDone={() => setSplash(true)} />}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="2" width="5" height="5" rx="1" fill="white"/>
              <rect x="9" y="2" width="5" height="5" rx="1" fill="white" opacity=".7"/>
              <rect x="2" y="9" width="5" height="5" rx="1" fill="white" opacity=".7"/>
              <rect x="9" y="9" width="5" height="5" rx="1" fill="white" opacity=".4"/>
            </svg>
          </div>
          <span className="header-title">SmartQueue</span>
          <span className="header-divider" />
          <span className="header-sub">AI Helpdesk Workload Optimizer</span>
        </div>
        <nav className="nav">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`nav-btn${active === t.id ? ' nav-btn--active' : ''}`}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="main">
        <div style={{ display: active === 'inbox'  ? 'contents' : 'none' }}><TicketInbox /></div>
        <div style={{ display: active === 'health' ? 'contents' : 'none' }}><QueueHealth /></div>
        <div style={{ display: active === 'bot'    ? 'contents' : 'none' }}><AIBot /></div>
      </main>
    </div>
  )
}

