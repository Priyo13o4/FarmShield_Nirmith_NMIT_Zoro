import { Database, AlertTriangle, BookOpen, Leaf } from 'lucide-react'

export default function SourceBadge({ source }) {
  let icon = <Database className="w-3 h-3" />
  let label = source
  let color = 'var(--text-color-muted)'

  switch (source) {
    case 'sensor_data':
      icon = <Database className="w-3 h-3" />
      label = 'Live Sensors'
      color = 'var(--color-primary)'
      break
    case 'historical_data':
      icon = <BookOpen className="w-3 h-3" />
      label = 'History'
      color = 'var(--color-primary)'
      break
    case 'alerts':
      icon = <AlertTriangle className="w-3 h-3" />
      label = 'Alerts'
      color = 'var(--color-danger)'
      break
    case 'farming_knowledge':
    case 'ai_model':
      icon = <Leaf className="w-3 h-3" />
      label = 'AI Assistant'
      color = 'var(--color-healthy)'
      break
    default:
      break
  }

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.25rem',
      fontSize: '0.75rem',
      fontWeight: '500',
      color,
      background: 'var(--color-surface)',
      border: '1px solid var(--border-color)',
      padding: '0.125rem 0.5rem',
      borderRadius: '9999px'
    }}>
      {icon}
      {label}
    </span>
  )
}