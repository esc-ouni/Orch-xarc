export default function StatsCards({ toolCount, scanResult, arbitrage }) {
  const stats = [
    { value: 57, label: 'Tools' },
    { value: 5, label: 'Namespaces' },
    {
      value: toolCount || '—',
      label: 'Tool Calls',
    },
    {
      value: arbitrage
        ? `$${arbitrage.best_opportunity?.margin?.toFixed(3) || '0'}`
        : '—',
      label: 'Best Margin',
    },
  ]

  return (
    <div className="stats-grid">
      {stats.map((s, i) => (
        <div className="stat-card" key={i}>
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  )
}
