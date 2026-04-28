import { useTranslation } from 'react-i18next'

const SEVERITY_VARIANT = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'critical',
}

const SEVERITY_LABEL_KEY = {
  INFO: 'common.info',
  WARNING: 'alerts.filter.warning',
  CRITICAL: 'alerts.filter.critical',
}

export default function AlertBadge({ severity = 'INFO' }) {
  const { t } = useTranslation()
  const normalized = String(severity).toUpperCase()
  const variant = SEVERITY_VARIANT[normalized] || 'info'
  const label = t(SEVERITY_LABEL_KEY[normalized] || SEVERITY_LABEL_KEY.INFO)

  return <span className={`surface-chip ${variant}`}>{label}</span>
}
