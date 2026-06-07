export default function SubagentView({ subagent }) {
  const isActive = subagent && subagent.status !== undefined

  return (
    <div className={`card subagent-panel ${isActive ? '' : 'inactive'}`}>
      <div className="subagent-header">
        <div className="subagent-icon">🧠</div>
        <span className="subagent-label">Arbitrage Subagent</span>
        {subagent?.status === 'running' && (
          <span className="badge badge-subagent">Running</span>
        )}
        {subagent?.status === 'complete' && (
          <span className="badge badge-math_logic">Complete</span>
        )}
      </div>

      {!isActive ? (
        <div className="empty-state" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.8rem' }}>
            Isolated context · Scoped to math_logic tools only
            <br />
            Activates during the Analyzing phase
          </div>
        </div>
      ) : (
        <div className="fade-in">
          <div className="subagent-detail">
            <span className="subagent-key">Context</span>
            <span className="subagent-value">Isolated StateGraph</span>
          </div>
          <div className="subagent-detail">
            <span className="subagent-key">Scoped Tools</span>
            <span className="subagent-value">{subagent.scoped_tools || 14} (math_logic only)</span>
          </div>
          <div className="subagent-detail">
            <span className="subagent-key">Message History</span>
            <span className="subagent-value">Own (not shared)</span>
          </div>
          {subagent.input_summary && (
            <div className="subagent-detail">
              <span className="subagent-key">Input</span>
              <span className="subagent-value" style={{ fontSize: '0.72rem' }}>{subagent.input_summary}</span>
            </div>
          )}
          {subagent.status === 'complete' && (
            <>
              <div className="subagent-detail">
                <span className="subagent-key">Opportunities</span>
                <span className="subagent-value" style={{ color: 'var(--accent-math)' }}>
                  {subagent.opportunities_found} found
                </span>
              </div>
              <div className="subagent-detail">
                <span className="subagent-key">Best Margin</span>
                <span className="subagent-value" style={{ color: 'var(--accent-math)' }}>
                  ${subagent.best_margin?.toFixed(3)}
                </span>
              </div>
              <div className="subagent-detail">
                <span className="subagent-key">Action</span>
                <span className="subagent-value" style={{
                  color: subagent.recommended_action === 'strong_buy'
                    ? 'var(--accent-math)' : 'var(--text-primary)'
                }}>
                  {subagent.recommended_action?.toUpperCase()}
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
