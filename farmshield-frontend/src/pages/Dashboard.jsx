import { Droplets, Thermometer, Zap, Bell } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import ControlCard from '../components/controls/ControlCard'
import SensorGrid from '../components/sensors/SensorGrid'
import { useFarm } from '../context/FarmContext'
import { getSensorStatus } from '../utils/sensorStatus'

const TONE_COLORS = {
  healthy: 'var(--color-healthy)',
  warning: 'var(--color-warning)',
  critical: 'var(--color-critical)',
  muted: 'var(--color-text-tertiary)',
  unknown: 'var(--color-text-tertiary)',
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null
  }
  return value % 1 === 0 ? String(value) : value.toFixed(1)
}

export default function Dashboard() {
  const { t } = useTranslation()
  const {
    sensorData,
    alerts,
    pumpOn,
    pumpMode,
    commandPump,
    commandMode,
    isLoading,
  } = useFarm()

  const [pendingAction, setPendingAction] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const rawSoil = sensorData?.soilPct ?? sensorData?.soilMoisturePct
  const soilValue = rawSoil != null ? Number(rawSoil) : null
  const rawTemp = sensorData?.tempC ?? sensorData?.temperatureC
  const tempValue = rawTemp != null ? Number(rawTemp) : null
  const activeAlertCount = alerts.filter((alert) => !alert.acknowledged).length

  const kpiItems = useMemo(
    () => [
      {
        key: 'soil',
        icon: Droplets,
        label: t('dashboard.kpi.soil'),
        value:
          formatNumber(soilValue) !== null
            ? `${formatNumber(soilValue)}${t('sensors.units.percent')}`
            : '—',
        tone: soilValue !== null ? getSensorStatus('soilPct', soilValue) : 'unknown',
      },
      {
        key: 'temperature',
        icon: Thermometer,
        label: t('dashboard.kpi.temperature'),
        value:
          formatNumber(tempValue) !== null
            ? `${formatNumber(tempValue)}${t('sensors.units.celsius')}`
            : '—',
        tone: tempValue !== null ? getSensorStatus('tempC', tempValue) : 'unknown',
      },
      {
        key: 'pump',
        icon: Zap,
        label: t('dashboard.kpi.pump'),
        value: pumpOn ? t('status.pumpOn') : t('status.pumpOff'),
        tone: pumpOn ? 'healthy' : 'muted',
      },
      {
        key: 'alerts',
        icon: Bell,
        label: t('dashboard.kpi.activeAlerts'),
        value: String(activeAlertCount),
        tone: activeAlertCount > 0 ? 'warning' : 'healthy',
      },
    ],
    [t, soilValue, tempValue, pumpOn, activeAlertCount]
  )

  async function handlePumpCommand(nextState) {
    setErrorMessage('')
    setPendingAction(nextState)

    try {
      await commandPump(nextState)
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setPendingAction('')
    }
  }

  async function handleModeCommand(nextMode) {
    setErrorMessage('')
    setPendingAction(nextMode)

    try {
      if (nextMode === 'AUTO' && pumpMode === 'MANUAL' && pumpOn) {
        // Turn off pump before switching to AUTO to prevent ESP32 stress
        await commandPump('OFF')
        await new Promise((resolve) => setTimeout(resolve, 500))
      }
      await commandMode(nextMode)
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setPendingAction('')
    }
  }

  return (
    <section className="page-stack" aria-label={t('nav.dashboard')}>
      <section className="kpi-grid" aria-label={t('nav.dashboard')}>
        {kpiItems.map((kpi) => {
          const Icon = kpi.icon
          const iconColor = TONE_COLORS[kpi.tone] || TONE_COLORS.unknown
          return (
            <article key={kpi.key} className="kpi-card">
              <div className="kpi-label">
                <Icon size={16} style={{ color: iconColor }} aria-hidden="true" />
                <span>{kpi.label}</span>
              </div>
              <div className={`kpi-value ${kpi.tone}`}>{kpi.value}</div>
            </article>
          )
        })}
      </section>

      <section className="dashboard-layout">
        <SensorGrid />

        <aside className="quick-controls" aria-label={t('controls.quickTitle')}>
          <ControlCard title={t('controls.quickTitle')}>
            <button
              type="button"
              className={`btn ${pumpOn ? 'btn-ghost' : 'btn-success'}`}
              onClick={() => handlePumpCommand(pumpOn ? 'OFF' : 'ON')}
              disabled={isLoading || Boolean(pendingAction) || pumpMode === 'AUTO'}
            >
              {pendingAction === 'ON' || pendingAction === 'OFF' ? (
                <span className="inline-spinner" aria-hidden="true" />
              ) : null}
              {pumpOn ? t('controls.turnOff') : t('controls.turnOn')}
            </button>

            <div className="segmented">
              <button
                type="button"
                className={`segment-btn ${pumpMode === 'AUTO' ? 'active' : ''}`}
                onClick={() => handleModeCommand('AUTO')}
                disabled={Boolean(pendingAction)}
              >
                {pendingAction === 'AUTO' ? (
                  <span className="inline-spinner" aria-hidden="true" />
                ) : null}
                {t('controls.auto')}
              </button>
              <button
                type="button"
                className={`segment-btn ${pumpMode === 'MANUAL' ? 'active' : ''}`}
                onClick={() => handleModeCommand('MANUAL')}
                disabled={Boolean(pendingAction)}
              >
                {pendingAction === 'MANUAL' ? (
                  <span className="inline-spinner" aria-hidden="true" />
                ) : null}
                {t('controls.manual')}
              </button>
            </div>

            {pumpMode === 'MANUAL' ? (
              <div className="warning-banner">{t('controls.manualWarning')}</div>
            ) : null}

            {errorMessage ? (
              <div className="inline-message error">{errorMessage}</div>
            ) : null}
          </ControlCard>
        </aside>
      </section>
    </section>
  )
}
