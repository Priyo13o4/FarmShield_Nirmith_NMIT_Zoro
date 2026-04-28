import { useTranslation } from 'react-i18next'

import Skeleton from '../common/Skeleton'
import StatusDot from '../common/StatusDot'

const STATUS_LABEL_KEY = {
  ok: 'status.healthy',
  warning: 'status.warning',
  critical: 'status.critical',
  offline: 'status.offline',
}

function formatSensorValue(value) {
  if (typeof value === 'boolean') {
    return value ? '1' : '0'
  }

  if (typeof value === 'number') {
    if (Number.isNaN(value)) return null;
    const hasFraction = value % 1 !== 0
    return hasFraction ? value.toFixed(1) : String(value)
  }

  if (value === null || value === undefined || value === '') {
    return null
  }

  return String(value)
}

export default function SensorCard({
  sensorKey,
  value,
  unit,
  icon: Icon,
  status = 'ok',
  label,
  isLoading,
}) {
  const { t } = useTranslation()
  const formattedValue = formatSensorValue(value)

  if (isLoading) {
    return (
      <article className="sensor-card" data-status="offline" aria-busy="true">
        <div className="sensor-head">
          <Skeleton width="8rem" height="1rem" />
          <Skeleton width="1.5rem" height="1.5rem" borderRadius="var(--radius-round)" />
        </div>
        <div className="sensor-value">
          <Skeleton width="7.5rem" height="2rem" />
        </div>
        <div className="sensor-status-row">
          <Skeleton width="5rem" height="0.875rem" />
          <Skeleton width="4rem" height="0.875rem" />
        </div>
      </article>
    )
  }

  return (
    <article className="sensor-card" data-status={status} data-sensor={sensorKey}>
      <header className="sensor-head">
        <div className="sensor-label">{label}</div>
        <Icon size={18} className={`sensor-icon ${status}`} aria-hidden="true" />
      </header>
      <div className="sensor-value">
        {formattedValue !== null ? (
          <>
            {formattedValue}
            {unit ? <span className="sensor-unit">{unit}</span> : null}
          </>
        ) : (
          t('common.noData')
        )}
      </div>
      <footer className="sensor-status-row">
        <span className="alert-meta">
          <StatusDot status={status} />
          {status !== 'unknown' && (
            <span>{t(STATUS_LABEL_KEY[status] || STATUS_LABEL_KEY.offline)}</span>
          )}
        </span>
      </footer>
    </article>
  )
}
