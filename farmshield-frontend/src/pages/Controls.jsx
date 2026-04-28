import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import ControlCard from '../components/controls/ControlCard'
import { useFarm } from '../context/FarmContext'

export default function Controls() {
  const { t } = useTranslation()
  const { 
    pumpOn,
    pumpMode, 
    commandPump, 
    commandMode, 
    silenceBuzzer,
    isLoading: isGlobalLoading 
  } = useFarm()

  const [pendingAction, setPendingAction] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [lastCommandTime, setLastCommandTime] = useState('')

  const pumpState = pumpOn ? 'ON' : 'OFF'

  async function handlePumpToggle() {
    const nextState = pumpState === 'ON' ? 'OFF' : 'ON'
    setErrorMessage('')
    setPendingAction(nextState)

    try {
      await commandPump(nextState)
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setPendingAction('')
    }
  }

  async function handleModeChange(nextMode) {
    setErrorMessage('')
    setPendingAction(nextMode)

    try {
      if (nextMode === 'AUTO' && pumpMode === 'MANUAL' && pumpOn) {
        // Turn off pump before switching to AUTO
        await commandPump('OFF')
        await new Promise((resolve) => setTimeout(resolve, 500))
      }
      await commandMode(nextMode)
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setPendingAction('')
    }
  }

  async function handleSilenceAlarm() {
    setErrorMessage('')
    setPendingAction('SILENCE')

    try {
      await silenceBuzzer()
      setLastCommandTime(new Date().toISOString())
    } catch (_error) {
      setErrorMessage(t('common.error'))
    } finally {
      setPendingAction('')
    }
  }

  return (
    <section className="controls-grid" aria-label={t('nav.controls')}>
      <ControlCard
        title={t('controls.pump')}
        titleAction={
          <span className={`surface-chip ${pumpOn ? '' : 'warning'}`}>
            {pumpOn ? t('status.pumpOn') : t('status.pumpOff')}
          </span>
        }
      >
        <p className="control-description">{t('controls.pumpDesc')}</p>
        <button
          type="button"
          className={`btn ${pumpOn ? 'btn-ghost' : 'btn-success'}`}
          onClick={handlePumpToggle}
          disabled={isGlobalLoading || Boolean(pendingAction) || pumpMode === 'AUTO'}
        >
          {pendingAction === 'ON' || pendingAction === 'OFF' ? (
            <span className="inline-spinner" aria-hidden="true" />
          ) : null}
          {pumpOn ? t('controls.turnOff') : t('controls.turnOn')}
        </button>

        {lastCommandTime ? (
          <div className="inline-message">
            {t('controls.lastCommand')} {new Date(lastCommandTime).toLocaleTimeString()}
          </div>
        ) : null}
      </ControlCard>

      <ControlCard title={t('controls.mode')}>
        <p className="control-description">{t('controls.modeDesc')}</p>
        <div className="segmented" role="group" aria-label={t('controls.mode')}>
          <button
            type="button"
            className={`segment-btn ${pumpMode === 'AUTO' ? 'active' : ''}`}
            onClick={() => handleModeChange('AUTO')}
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
            onClick={() => handleModeChange('MANUAL')}
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
      </ControlCard>

      <ControlCard title={t('controls.buzzer')}>
        <p className="control-description">{t('controls.buzzerDesc')}</p>
        <button
          type="button"
          className="btn btn-danger"
          onClick={handleSilenceAlarm}
          disabled={Boolean(pendingAction)}
        >
          {pendingAction === 'SILENCE' ? (
            <span className="inline-spinner" aria-hidden="true" />
          ) : null}
          {t('controls.silence')}
        </button>
      </ControlCard>

      {errorMessage ? (
        <div className="inline-message error" style={{ gridColumn: '1 / -1' }}>
          {errorMessage}
        </div>
      ) : null}
    </section>
  )
}

