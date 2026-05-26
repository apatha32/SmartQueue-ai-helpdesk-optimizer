import { useState } from 'react'
import QueueStats from './components/QueueStats'
import JobSubmit from './components/JobSubmit'
import JobList from './components/JobList'
import RAGChat from './components/RAGChat'
import DeadLetterPanel from './components/DeadLetterPanel'
import './App.css'

const TABS = [
  { id: 'queue', label: 'Queue' },
  { id: 'rag', label: 'RAG Chat' },
  { id: 'dlq', label: 'Dead Letter' },
]

export default function App() {
  const [active, setActive] = useState('queue')

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="header-hex">⬡</span>
          <span className="header-title">DTQ</span>
          <span className="header-sub">Distributed Task Queue</span>
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
        {active === 'queue' && (
          <div className="page">
            <QueueStats />
            <div className="two-col">
              <JobSubmit />
              <JobList />
            </div>
          </div>
        )}
        {active === 'rag'  && <RAGChat />}
        {active === 'dlq'  && <DeadLetterPanel />}
      </main>
    </div>
  )
}
