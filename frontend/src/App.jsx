import { useState } from 'react'
import TicketInbox from './components/TicketInbox'
import QueueHealth from './components/QueueHealth'
import AIBot from './components/AIBot'
import './App.css'

const TABS = [
  { id: 'inbox',  label: '📥 Ticket Inbox' },
  { id: 'health', label: '📊 Queue Health' },
  { id: 'bot',    label: '🤖 AI Bot'        },
]

export default function App() {
  const [active, setActive] = useState('inbox')

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="header-hex">⚡</span>
          <span className="header-title">SmartQueue</span>
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

