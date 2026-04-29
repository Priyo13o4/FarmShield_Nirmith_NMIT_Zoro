import { BarChart2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import SensorChart from '../components/charts/SensorChart'
import EmptyState from '../components/common/EmptyState'
import { api, getDeviceId } from '../services/api'

const RANGE_OPTIONS = [
  { key: '1h', hours: 1 },
  { key: '6h', hours: 6 },
  { key: '24h', hours: 24 },
  { key: '7d', hours: 168 },
]

const SENSOR_OPTIONS = ['soilPct', 'tempC', 'humidityPct', 'tdsPpm', 'rainMm']
const MAX_SELECTED_SENSORS = 3
const HISTORY_LIMIT = 160

function normalizeHistoryRows(payload) {
  const rows = Array.isArray(payload) ? payload : payload?.data || payload?.items || []
  return rows.map((item) => {
    const timestamp = item.timestamp || item.createdAt || new Date().toISOString()
    return {
      ...item,
      timestamp,
      timestampLabel: new Date(timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }
  })
}

export default function History() {
  const { t } = useTranslation()
  const [activeRange, setActiveRange] = useState('24h')
  const [selectedSensors, setSelectedSensors] = useState(['soilPct', 'tempC'])
  const [historyRows, setHistoryRows] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [isExporting, setIsExporting] = useState(false)

  const [hasFetched, setHasFetched] = useState(false)

  const fetchHistory = useCallback(async () => {
    const range = RANGE_OPTIONS.find((item) => item.key === activeRange) || RANGE_OPTIONS[2]
    setIsLoading(true)
    setErrorMessage('')

    try {
      const response = await api.sensors.history({
        deviceId: getDeviceId(),
        hours: range.hours,
        limit: HISTORY_LIMIT,
        offset: 0,
      })
      setHistoryRows(normalizeHistoryRows(response))
    } catch (_error) {
      setErrorMessage(t('common.error'))
      setHistoryRows([])
    } finally {
      setIsLoading(false)
      setHasFetched(true)
    }
  }, [activeRange, t])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  function toggleSensor(sensorKey) {
    setSelectedSensors((previous) => {
      if (previous.includes(sensorKey)) {
        return previous.filter((key) => key !== sensorKey)
      }

      if (previous.length >= MAX_SELECTED_SENSORS) {
        return previous
      }

      return [...previous, sensorKey]
    })
  }

  async function handleExport() {
    const range = RANGE_OPTIONS.find((item) => item.key === activeRange) || RANGE_OPTIONS[2]
    setIsExporting(true)
    setErrorMessage('')

    try {
      await api.sensors.export({
        deviceId: getDeviceId(),
        hours: range.hours,
        limit: HISTORY_LIMIT,
      })
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setIsExporting(false)
    }
  }

  const emptyState = useMemo(
    () => {
      if (selectedSensors.length === 0) {
        return (
          <EmptyState
            icon={BarChart2}
            title={t('common.noData')}
            description={t('history.selectSensors')}
          />
        )
      }
      return (
        <EmptyState
          icon={BarChart2}
          title={t('common.noData')}
          description={t('history.noDataRange') || 'No data available for selected range'}
        />
      )
    },
    [t, selectedSensors.length]
  )

  return (
    <section className="page-stack" aria-label={t('history.title')}>
      <header className="page-header-row">
        <div className="pill-row">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={`pill ${activeRange === option.key ? 'active' : ''}`}
              onClick={() => setActiveRange(option.key)}
            >
              {t(`history.range.${option.key}`)}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleExport}
          disabled={isExporting}
        >
          {isExporting ? <span className="inline-spinner" aria-hidden="true" /> : null}
          {t('history.export')}
        </button>
      </header>

      <div className="filter-tabs" aria-label={t('history.selectSensors')}>
        {SENSOR_OPTIONS.map((sensorKey) => (
          <button
            key={sensorKey}
            type="button"
            className={`filter-tab ${selectedSensors.includes(sensorKey) ? 'active' : ''}`}
            onClick={() => toggleSensor(sensorKey)}
          >
            {t(`sensors.${sensorKey.replace('Pct', '').replace('Mm', '').replace('C', '').replace('Ppm', '')}`, sensorKey)}
          </button>
        ))}
      </div>

      {hasFetched && errorMessage ? (
        <EmptyState
          icon={BarChart2}
          title={errorMessage}
          description={t('common.retry')}
        />
      ) : (
        <section className="chart-card">
          <SensorChart
            data={historyRows}
            selectedSensors={selectedSensors}
            isLoading={isLoading}
            emptyState={emptyState}
          />
        </section>
      )}
    </section>
  )
}
