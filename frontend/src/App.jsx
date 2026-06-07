import './index.css'
import Header from './components/Header'
import ScanControl from './components/ScanControl'
import StatsCards from './components/StatsCards'
import ToolTimeline from './components/ToolTimeline'
import SubagentView from './components/SubagentView'
import ArbitrageResults from './components/ArbitrageResults'
import ToolRegistry from './components/ToolRegistry'
import { useScanStream } from './hooks/useScanStream'

export default function App() {
  const {
    events, phase, phaseIndex, isRunning,
    subagent, arbitrage, scanResult, toolCount,
    startScan, PHASES,
  } = useScanStream()

  return (
    <div className="app">
      <Header />

      <div style={{ marginTop: 20 }}>
        <StatsCards toolCount={toolCount} scanResult={scanResult} arbitrage={arbitrage} />
      </div>

      <div className="dashboard-grid">
        <div className="full-width">
          <ScanControl
            onStartScan={startScan}
            isRunning={isRunning}
            phase={phase}
            phaseIndex={phaseIndex}
            PHASES={PHASES}
            toolCount={toolCount}
            scanResult={scanResult}
          />
        </div>

        <ToolTimeline events={events} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <SubagentView subagent={subagent} />
          <ArbitrageResults arbitrage={arbitrage} />
        </div>

        <div className="full-width">
          <ToolRegistry />
        </div>
      </div>
    </div>
  )
}
