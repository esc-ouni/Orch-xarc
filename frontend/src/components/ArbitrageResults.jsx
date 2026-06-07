export default function ArbitrageResults({ arbitrage }) {
  if (!arbitrage) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Arbitrage Results</span>
        </div>
        <div className="empty-state">
          Results will appear after the subagent analysis
        </div>
      </div>
    )
  }

  const best = arbitrage.best_opportunity
  const opps = arbitrage.opportunities || []

  return (
    <div className="card fade-in">
      <div className="card-header">
        <span className="card-title">Arbitrage Results</span>
        <span className="badge badge-math_logic">
          {opps.length} {opps.length === 1 ? 'opportunity' : 'opportunities'}
        </span>
      </div>

      {opps.map((opp, i) => (
        <div className="arb-card" key={i}>
          <div className="arb-header">
            <span className="arb-strategy">{opp.strategy}</span>
            <span className="arb-margin">+${opp.margin?.toFixed(3)}</span>
          </div>

          <div className="arb-legs">
            <div className="arb-leg">
              <div className="arb-leg-platform">Polymarket</div>
              <div className="arb-leg-cost" style={{ color: 'var(--accent-polymarket)' }}>
                {opp.poly_side} ${opp.poly_cost?.toFixed(3)}
              </div>
            </div>
            <div className="arb-plus">+</div>
            <div className="arb-leg">
              <div className="arb-leg-platform">Kalshi</div>
              <div className="arb-leg-cost" style={{ color: 'var(--accent-kalshi)' }}>
                {opp.kalshi_side} ${opp.kalshi_cost?.toFixed(3)}
              </div>
            </div>
          </div>

          <div className="arb-bottom">
            <span>
              Total: <strong style={{ fontFamily: 'var(--font-mono)' }}>${opp.total_cost?.toFixed(3)}</strong>
            </span>
            <span>
              Confidence: {(arbitrage.confidence * 100).toFixed(0)}%
              <span className="confidence-bar">
                <span className="confidence-fill" style={{ width: `${arbitrage.confidence * 100}%` }} />
              </span>
            </span>
            <span style={{
              color: arbitrage.recommended_action === 'strong_buy'
                ? 'var(--accent-math)' : 'var(--text-secondary)',
              fontWeight: 600,
            }}>
              {arbitrage.recommended_action?.toUpperCase()}
            </span>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 12, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        {arbitrage.total_checks} checks performed across all Kalshi markets
      </div>
    </div>
  )
}
