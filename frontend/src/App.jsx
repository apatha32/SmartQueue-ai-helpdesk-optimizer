import { useState } from 'react'
import TicketInbox from './components/TicketInbox'
import QueueHealth from './components/QueueHealth'
import AIBot from './components/AIBot'
import './App.css'

const TABS = [
  { id: 'inbox',  label: 'Ticket Inbox' },
  { id: 'health', label: 'Queue Health' },
  { id: 'bot',    label: 'AI Assistant' },
]

export default function App() {
  const [active, setActive] = useState('inbox')

  return (
    <div className="app">
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
        {active === 'inbox'  && <TicketInbox />}
        {active === 'health' && <QueueHealth />}
        {active === 'bot'    && <AIBot />}
      </main>
    </div>
  )
}

