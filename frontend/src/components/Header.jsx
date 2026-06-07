import { useState, useEffect } from 'react'

export default function Header() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch('/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth(null))

    const interval = setInterval(() => {
      fetch('/health')
        .then(r => r.json())
        .then(setHealth)
        .catch(() => setHealth(null))
    }, 15000)

    return () => clearInterval(interval)
  }, [])

  return (
    <header className="header">
      <div className="header-left">
        <span className="header-logo">Orch-xarc</span>
        <span className="header-subtitle">Autonomous Arbitrage Agent</span>
      </div>
      <div className="header-right">
        <div className={`status-dot ${health ? '' : 'offline'}`} />
        <span className="header-meta">
          {health
            ? `${health.tool_count} tools · ${health.llm_model} · v${health.version}`
            : 'Connecting…'}
        </span>
      </div>
    </header>
  )
}
