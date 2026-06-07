export default function ScanControl({ onStartDemo, isRunning, phase, phaseIndex, PHASES, toolCount, scanResult }) {
  const phaseLabels = { init: 'Init', gathering: 'Gathering', analyzing: 'Analyzing', complete: 'Complete' }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Scan Control</span>
        {toolCount > 0 && (
          <span className="header-meta">{toolCount} tool calls</span>
        )}
      </div>

      <button
        className="btn btn-primary"
        onClick={onStartDemo}
        disabled={isRunning}
      >
        {isRunning ? '⏳ Scanning…' : '▶ Run Demo Scan'}
      </button>

      {phase && (
        <>
          <div className="phase-bar">
            {PHASES.map((p, i) => (
              <div
                key={p}
                className={`phase-step ${i < phaseIndex ? 'done' : ''} ${i === phaseIndex ? 'active' : ''}`}
              />
            ))}
          </div>
          <div className="phase-labels">
            {PHASES.map((p, i) => (
              <span
                key={p}
                className={`phase-label ${i < phaseIndex ? 'done' : ''} ${i === phaseIndex ? 'active' : ''}`}
              >
                {phaseLabels[p]}
              </span>
            ))}
          </div>
        </>
      )}

      {scanResult && (
        <div style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          ✅ Completed in {(scanResult.total_duration_ms / 1000).toFixed(1)}s · {scanResult.total_tool_calls} tool calls · {scanResult.opportunities_found} opportunity found
        </div>
      )}
    </div>
  )
}
