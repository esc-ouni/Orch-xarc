import { useEffect, useRef } from 'react'

export default function ToolTimeline({ events }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  if (events.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Tool Call Timeline</span>
        </div>
        <div className="empty-state">
          <div className="empty-icon">🔧</div>
          Run a scan to see tool calls appear here in real-time
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Tool Call Timeline</span>
        <span className="header-meta">{events.length} events</span>
      </div>
      <div className="timeline" ref={scrollRef}>
        {events.map((event, i) => (
          <TimelineItem key={i} event={event} />
        ))}
      </div>
    </div>
  )
}

function TimelineItem({ event }) {
  if (event.type === 'subagent_spawn') {
    return (
      <div className="timeline-item" style={{ borderLeft: '2px solid var(--accent-subagent)', marginLeft: 0, paddingLeft: 12 }}>
        <div className="timeline-dot" style={{ background: 'var(--accent-subagent)' }} />
        <div className="timeline-content">
          <div className="timeline-tool-name" style={{ color: 'var(--accent-subagent)' }}>
            🧠 Subagent Spawned
          </div>
          <div className="timeline-meta">
            <span className="badge badge-subagent">isolated</span>
            <span>{event.scoped_tools} scoped tools</span>
          </div>
        </div>
      </div>
    )
  }

  const ns = event.namespace || 'ops'

  return (
    <div className={`timeline-item ${event.is_subagent ? 'subagent' : ''}`}>
      <div className={`timeline-dot ${ns}`} />
      <div className="timeline-content">
        <div className="timeline-tool-name">{event.tool_name}</div>
        <div className="timeline-meta">
          <span className={`badge badge-${ns}`}>{ns}</span>
          <span className="timeline-duration">{event.duration_ms}ms</span>
          <span>{(event.elapsed_ms / 1000).toFixed(1)}s</span>
        </div>
      </div>
    </div>
  )
}
