import { ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import AlertRow from '../components/alerts/AlertRow'
import EmptyState from '../components/common/EmptyState'
import { useFarm } from '../context/FarmContext'
import { api, getDeviceId } from '../services/api'

const FILTER_OPTIONS = ['all', 'warning', 'critical', 'unread']

function mergeAlerts(serverAlerts, liveAlerts) {
  const map = new Map()
  ;[...liveAlerts, ...serverAlerts].forEach((alert) => {
    const key = alert.id || `${alert.timestamp}-${alert.message}`
    if (!map.has(key)) {
      map.set(key, alert)
    }
  })
  return [...map.values()]
}

export default function Alerts() {
  const { t } = useTranslation()
  const {
    alerts: liveAlerts,
    clearUnread,
    acknowledgeAlertLocal,
  } = useFarm()

  const [serverAlerts, setServerAlerts] = useState([])
  const [activeFilter, setActiveFilter] = useState('all')
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [acknowledgingId, setAcknowledgingId] = useState('')

  useEffect(() => {
    clearUnread()
  }, [clearUnread])

  useEffect(() => {
    let mounted = true

    async function fetchAlerts() {
      setIsLoading(true)
      setErrorMessage('')

      try {
        const response = await api.alerts.list({
          deviceId: getDeviceId(),
          limit: 100,
          unacknowledgedOnly: false,
        })
        const rows = Array.isArray(response) ? response : response?.data || []
        if (mounted) {
          setServerAlerts(rows)
        }
      } catch (_error) {
        if (mounted) {
          setErrorMessage(t('common.error'))
        }
      } finally {
        if (mounted) {
          setIsLoading(false)
        }
      }
    }

    fetchAlerts()

    return () => {
      mounted = false
    }
  }, [t])

  const combinedAlerts = useMemo(
    () => mergeAlerts(serverAlerts, liveAlerts),
    [serverAlerts, liveAlerts]
  )

  const filteredAlerts = useMemo(() => {
    if (activeFilter === 'warning') {
      return combinedAlerts.filter((item) => item.severity === 'WARNING')
    }
    if (activeFilter === 'critical') {
      return combinedAlerts.filter((item) => item.severity === 'CRITICAL')
    }
    if (activeFilter === 'unread') {
      return combinedAlerts.filter((item) => !item.acknowledged)
    }
    return combinedAlerts
  }, [activeFilter, combinedAlerts])

  async function handleAcknowledge(alertId) {
    setAcknowledgingId(String(alertId))
    setErrorMessage('')

    const previousServerAlerts = serverAlerts
    setServerAlerts((previous) =>
      previous.map((item) =>
        String(item.id) === String(alertId)
          ? {
              ...item,
              acknowledged: true,
            }
          : item
      )
    )
    acknowledgeAlertLocal(alertId)

    try {
      await api.alerts.acknowledge(alertId)
    } catch (_error) {
      setServerAlerts(previousServerAlerts)
      setErrorMessage(t('common.error'))
    } finally {
      setAcknowledgingId('')
    }
  }

  if (!isLoading && !filteredAlerts.length) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title={t('alerts.noAlerts')}
        description={t('alerts.noAlertsDesc')}
      />
    )
  }

  return (
    <section className="page-stack" aria-label={t('alerts.title')}>
      <div className="pill-row">
        {FILTER_OPTIONS.map((filter) => (
          <button
            key={filter}
            type="button"
            className={`pill ${activeFilter === filter ? 'active' : ''}`}
            onClick={() => setActiveFilter(filter)}
          >
            {t(`alerts.filter.${filter}`)}
          </button>
        ))}
      </div>

      {errorMessage ? <div className="inline-message error">{errorMessage}</div> : null}

      <div className="alert-list">
        {filteredAlerts.map((alert) => (
          <AlertRow
            key={alert.id || `${alert.timestamp}-${alert.message}`}
            alert={alert}
            onAcknowledge={handleAcknowledge}
            isSubmitting={acknowledgingId === String(alert.id)}
          />
        ))}
      </div>
    </section>
  )
}
