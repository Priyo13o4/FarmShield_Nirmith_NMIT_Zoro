const STATUS_CLASS = {
  ok: 'ok',
  warning: 'warning',
  critical: 'critical',
  offline: 'offline',
  unknown: 'unknown',
}

export default function StatusDot({ status = 'offline' }) {
  const className = STATUS_CLASS[status] || STATUS_CLASS.offline
  return <span className={`status-dot ${className}`} aria-hidden="true" />
}
