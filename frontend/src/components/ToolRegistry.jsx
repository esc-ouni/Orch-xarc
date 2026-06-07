import { useState, useEffect } from 'react'

const NS_COLORS = {
  polymarket: 'var(--accent-polymarket)',
  kalshi: 'var(--accent-kalshi)',
  math_logic: 'var(--accent-math)',
  execution: 'var(--accent-execution)',
  ops: 'var(--accent-ops)',
}

export default function ToolRegistry() {
  const [data, setData] = useState(null)
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    fetch('/tools/stats')
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
  }, [])

  if (!data) return null

  const toggle = (ns) => setExpanded(prev => ({ ...prev, [ns]: !prev[ns] }))

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Tool Registry</span>
        <span className="header-meta">{data.total} tools · {Object.keys(data.namespaces).length} namespaces</span>
      </div>

      {Object.entries(data.namespaces).map(([ns, info]) => (
        <div className="registry-namespace" key={ns}>
          <div className="registry-header" onClick={() => toggle(ns)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: NS_COLORS[ns],
              }} />
              <span className={`badge badge-${ns}`}>{ns}</span>
            </div>
            <span className="registry-count">
              {info.count} tools {expanded[ns] ? '▾' : '▸'}
            </span>
          </div>
          {expanded[ns] && (
            <div className="registry-tools fade-in">
              {info.tools.map(name => (
                <div className="registry-tool" key={name}>{name}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
