import { useState, useCallback, useRef } from 'react'

const PHASES = ['init', 'gathering', 'analyzing', 'complete']

export function useScanStream() {
  const [events, setEvents] = useState([])
  const [phase, setPhase] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [subagent, setSubagent] = useState(null)
  const [arbitrage, setArbitrage] = useState(null)
  const [scanResult, setScanResult] = useState(null)
  const [toolCount, setToolCount] = useState(0)
  const eventSourceRef = useRef(null)

  const reset = useCallback(() => {
    setEvents([])
    setPhase(null)
    setSubagent(null)
    setArbitrage(null)
    setScanResult(null)
    setToolCount(0)
  }, [])

  const startDemo = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    reset()
    setIsRunning(true)

    const es = new EventSource('/scan/demo')
    eventSourceRef.current = es

    es.addEventListener('phase_change', (e) => {
      const data = JSON.parse(e.data)
      setPhase(data.phase)
    })

    es.addEventListener('tool_call', (e) => {
      const data = JSON.parse(e.data)
      setEvents(prev => [...prev, { type: 'tool_call', ...data }])
      setToolCount(prev => prev + 1)
    })

    es.addEventListener('subagent_spawn', (e) => {
      const data = JSON.parse(e.data)
      setSubagent({ status: 'running', ...data })
      setEvents(prev => [...prev, { type: 'subagent_spawn', ...data }])
    })

    es.addEventListener('subagent_complete', (e) => {
      const data = JSON.parse(e.data)
      setSubagent(prev => ({ ...prev, status: 'complete', ...data }))
    })

    es.addEventListener('arbitrage_result', (e) => {
      const data = JSON.parse(e.data)
      setArbitrage(data)
    })

    es.addEventListener('scan_complete', (e) => {
      const data = JSON.parse(e.data)
      setScanResult(data)
      setIsRunning(false)
      es.close()
    })

    es.onerror = () => {
      setIsRunning(false)
      es.close()
    }
  }, [reset])

  const phaseIndex = phase ? PHASES.indexOf(phase) : -1

  return {
    events,
    phase,
    phaseIndex,
    isRunning,
    subagent,
    arbitrage,
    scanResult,
    toolCount,
    startDemo,
    PHASES,
  }
}
