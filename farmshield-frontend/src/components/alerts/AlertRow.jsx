import { useTranslation } from 'react-i18next'

import StatusDot from '../common/StatusDot'
import AlertBadge from './AlertBadge'

const ALERT_STATUS = {
  INFO: 'ok',
  WARNING: 'warning',
  CRITICAL: 'critical',
}

export default function AlertRow({ alert, onAcknowledge, isSubmitting }) {
  const { t, i18n } = useTranslation()
  const severity = String(alert.severity || 'INFO').toUpperCase()
  const status = ALERT_STATUS[severity] || 'ok'
  const timestamp = alert.timestamp || alert.createdAt || new Date().toISOString()
  const message = alert.message || t('common.noData')

  return (
    <article className={`alert-row ${alert.acknowledged ? 'acknowledged' : ''}`}>
      <div className="alert-meta">
        <StatusDot status={status} />
        <AlertBadge severity={severity} />
      </div>
      <time className="alert-timestamp" dateTime={timestamp}>
        {new Intl.DateTimeFormat(i18n.language, {
          dateStyle: 'medium',
          timeStyle: 'short',
        }).format(new Date(timestamp))}
      </time>
      <div className="alert-message">{message}</div>
      {alert.acknowledged ? null : (
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => onAcknowledge(alert.id)}
          disabled={isSubmitting}
        >
          {isSubmitting ? <span className="inline-spinner" aria-hidden="true" /> : null}
          {t('alerts.acknowledge')}
        </button>
      )}
    </article>
  )
}
