import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import ControlCard from '../components/controls/ControlCard'
import { useFarm } from '../context/FarmContext'
import { api } from '../services/api'

export default function Controls() {
  const { t } = useTranslation()
  const { sensorData, pumpMode, setPumpMode } = useFarm()

  const [pumpState, setPumpState] = useState(
    sensorData?.pumpState || (sensorData?.pumpOn ? 'ON' : 'OFF')
  )
  const [lastCommandTime, setLastCommandTime] = useState('')

  const [pumpLoading, setPumpLoading] = useState(false)
  const [modeLoading, setModeLoading] = useState(false)
  const [buzzerLoading, setBuzzerLoading] = useState(false)

  const [pumpError, setPumpError] = useState('')
  const [modeError, setModeError] = useState('')
  const [buzzerError, setBuzzerError] = useState('')

  async function handlePumpToggle() {
    const previousState = pumpState
    const nextState = previousState === 'ON' ? 'OFF' : 'ON'

    setPumpLoading(true)
    setPumpError('')
    setPumpState(nextState)

    try {
      await api.control.pump(nextState)
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setPumpState(previousState)
      setPumpError(t('common.error'))
    } finally {
      setPumpLoading(false)
    }
  }

  async function handleModeChange(nextMode) {
    const previousMode = pumpMode

    setModeLoading(true)
    setModeError('')
    setPumpMode(nextMode)

    try {
      await api.control.mode(nextMode)
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setPumpMode(previousMode)
      setModeError(t('common.error'))
    } finally {
      setModeLoading(false)
    }
  }

  async function handleSilenceAlarm() {
    setBuzzerLoading(true)
    setBuzzerError('')

    try {
      await api.control.buzzer()
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setBuzzerError(t('common.error'))
    } finally {
      setBuzzerLoading(false)
    }
  }

  return (
    <section className="controls-grid" aria-label={t('nav.controls')}>
      <ControlCard
        title={t('controls.pump')}
        titleAction={
          <span className={`surface-chip ${pumpState === 'ON' ? '' : 'warning'}`}>
            {pumpState === 'ON' ? t('status.pumpOn') : t('status.pumpOff')}
          </span>
        }
      >
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted, var(--color-text-secondary))', marginTop: '-0.5rem', marginBottom: '1rem' }}>{t('controls.pumpDesc')}</p>
        <button
          type="button"
          className={`btn ${pumpState === 'ON' ? 'btn-ghost' : 'btn-success'}`}
          onClick={handlePumpToggle}
          disabled={pumpLoading}
        >
          {pumpLoading ? <span className="inline-spinner" aria-hidden="true" /> : null}
          {pumpState === 'ON' ? t('controls.turnOff') : t('controls.turnOn')}
        </button>

        {lastCommandTime ? (
          <div className="inline-message">
            {t('controls.lastCommand')} {new Date(lastCommandTime).toLocaleTimeString()}
          </div>
        ) : null}

        {pumpError ? <div className="inline-message error">{pumpError}</div> : null}
      </ControlCard>

      <ControlCard title={t('controls.mode')}>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted, var(--color-text-secondary))', marginTop: '-0.5rem', marginBottom: '1rem' }}>{t('controls.modeDesc')}</p>
        <div className="segmented" role="group" aria-label={t('controls.mode')}>
          <button
            type="button"
            className={`segment-btn ${pumpMode === 'AUTO' ? 'active' : ''}`}
            onClick={() => handleModeChange('AUTO')}
            disabled={modeLoading}
          >
            {modeLoading && pumpMode === 'AUTO' ? (
              <span className="inline-spinner" aria-hidden="true" />
            ) : null}
            {t('controls.auto')}
          </button>
          <button
            type="button"
            className={`segment-btn ${pumpMode === 'MANUAL' ? 'active' : ''}`}
            onClick={() => handleModeChange('MANUAL')}
            disabled={modeLoading}
          >
            {modeLoading && pumpMode === 'MANUAL' ? (
              <span className="inline-spinner" aria-hidden="true" />
            ) : null}
            {t('controls.manual')}
          </button>
        </div>

        {pumpMode === 'MANUAL' ? (
          <div className="warning-banner">{t('controls.manualWarning')}</div>
        ) : null}

        {modeError ? <div className="inline-message error">{modeError}</div> : null}
      </ControlCard>

      <ControlCard title={t('controls.buzzer')}>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted, var(--color-text-secondary))', marginTop: '-0.5rem', marginBottom: '1rem' }}>{t('controls.buzzerDesc')}</p>
        <button
          type="button"
          className="btn btn-danger"
          onClick={handleSilenceAlarm}
          disabled={buzzerLoading}
        >
          {buzzerLoading ? <span className="inline-spinner" aria-hidden="true" /> : null}
          {t('controls.silence')}
        </button>

        {buzzerError ? <div className="inline-message error">{buzzerError}</div> : null}
      </ControlCard>
    </section>
  )
}
