import { Eye, EyeOff, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, configureApi, getApiConfig, getDeviceIds, setDeviceIds } from '../services/api'
import { useFarm } from '../context/FarmContext'
import { loadGoogleFont } from '../i18n'

const LANGUAGE_OPTIONS = [
  { code: 'en', labelKey: 'settings.languageNames.en' },
  { code: 'kn', labelKey: 'settings.languageNames.kn' },
  { code: 'hi', labelKey: 'settings.languageNames.hi' },
  { code: 'te', labelKey: 'settings.languageNames.te' },
]

export default function Settings() {
  const { t, i18n } = useTranslation()
  const { activeNodeId, switchActiveNode } = useFarm()

  const [apiUrl, setApiUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [deviceIds, setLocalDeviceIds] = useState([])
  const [newDeviceId, setNewDeviceId] = useState('')
  const [language, setLanguage] = useState('en')
  const [showApiKey, setShowApiKey] = useState(false)

  const [isTesting, setIsTesting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [testResult, setTestResult] = useState('')
  const [testResultType, setTestResultType] = useState('')
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    const config = getApiConfig()
    const storedLanguage = localStorage.getItem('fs_language') || i18n.resolvedLanguage || 'en'

    setApiUrl(config.url)
    setApiKey(config.apiKey)
    setLocalDeviceIds(getDeviceIds())
    setLanguage(storedLanguage)
  }, [i18n.resolvedLanguage])

  function handleAddDevice() {
    const id = newDeviceId.trim()
    if (!id || deviceIds.includes(id)) return
    const next = [...deviceIds, id]
    setLocalDeviceIds(next)
    setNewDeviceId('')
  }

  function handleRemoveDevice(id) {
    if (deviceIds.length <= 1) return // Must keep at least 1
    const next = deviceIds.filter((d) => d !== id)
    setLocalDeviceIds(next)
    // If the removed node was active, switch to first available
    if (activeNodeId === id && next.length > 0) {
      switchActiveNode(next[0])
    }
  }

  function handleDeviceKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddDevice()
    }
  }

  async function handleTestConnection() {
    setIsTesting(true)
    setSaveMessage('')
    setTestResult('')
    setTestResultType('')

    try {
      await api.health.check({ url: apiUrl, apiKey })
      setTestResult(t('settings.connectionOk'))
      setTestResultType('success')
    } catch (_error) {
      setTestResult(t('settings.connectionFail'))
      setTestResultType('error')
    } finally {
      setIsTesting(false)
    }
  }

  async function handleSaveSettings() {
    setIsSaving(true)
    setSaveMessage('')

    try {
      configureApi({ url: apiUrl, apiKey })
      setDeviceIds(deviceIds)
      localStorage.setItem('fs_language', language)
      await i18n.changeLanguage(language)
      loadGoogleFont(language)
      setSaveMessage(t('settings.saved'))
    } catch (_error) {
      setSaveMessage(t('common.error'))
    } finally {
      setIsSaving(false)
    }
  }

  async function handleLanguageChange(nextLanguage) {
    setLanguage(nextLanguage)
    await i18n.changeLanguage(nextLanguage)
    loadGoogleFont(nextLanguage)
  }

  return (
    <section className="form-card" aria-label={t('settings.title')}>
      <div className="form-grid">
        <div className="form-field">
          <label className="field-label" htmlFor="api-url">
            {t('settings.apiUrl')}
          </label>
          <input
            id="api-url"
            className="field-input"
            type="text"
            placeholder={t('settings.apiPlaceholder')}
            value={apiUrl}
            onChange={(event) => setApiUrl(event.target.value)}
          />
        </div>

        <div className="form-field">
          <label className="field-label" htmlFor="api-key">
            {t('settings.apiKey')}
          </label>
          <div className="field-input-wrap">
            <input
              id="api-key"
              className="field-input"
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
            <button
              type="button"
              className="input-icon-btn"
              onClick={() => setShowApiKey((current) => !current)}
              aria-label={showApiKey ? t('settings.hide') : t('settings.show')}
            >
              {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {/* Multi-node Device IDs */}
        <div className="form-field">
          <span className="field-label">
            {t('settings.deviceId')}
            <span style={{ color: 'var(--color-text-tertiary)', fontWeight: 400, marginLeft: 'var(--space-2)' }}>
              ({deviceIds.length} {deviceIds.length === 1 ? 'node' : 'nodes'})
            </span>
          </span>

          <div className="node-list">
            {deviceIds.map((id) => (
              <div
                key={id}
                className={`node-chip ${id === activeNodeId ? 'active' : ''}`}
                onClick={() => switchActiveNode(id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && switchActiveNode(id)}
              >
                <span className="node-chip-dot" />
                <span className="node-chip-label">{id}</span>
                {deviceIds.length > 1 && (
                  <button
                    type="button"
                    className="node-chip-remove"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveDevice(id)
                    }}
                    aria-label={`Remove ${id}`}
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="node-add-row">
            <input
              className="field-input"
              type="text"
              placeholder="esp32-node-2"
              value={newDeviceId}
              onChange={(e) => setNewDeviceId(e.target.value)}
              onKeyDown={handleDeviceKeyDown}
            />
            <button
              type="button"
              className="btn btn-ghost node-add-btn"
              onClick={handleAddDevice}
              disabled={!newDeviceId.trim()}
            >
              <Plus size={16} />
              {t('settings.addNode') || 'Add Node'}
            </button>
          </div>
        </div>

        <div className="form-field">
          <span className="field-label">{t('settings.language')}</span>
          <div className="lang-switch-large" role="group" aria-label={t('settings.language')}>
            {LANGUAGE_OPTIONS.map((option) => (
              <button
                key={option.code}
                type="button"
                className={`lang-btn ${language === option.code ? 'active' : ''}`}
                onClick={() => handleLanguageChange(option.code)}
              >
                {t(option.labelKey)}
              </button>
            ))}
          </div>
        </div>

        <div className="page-header-row">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={handleTestConnection}
            disabled={isTesting}
          >
            {isTesting ? <span className="inline-spinner" aria-hidden="true" /> : null}
            {t('settings.testConnection')}
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSaveSettings}
            disabled={isSaving}
          >
            {isSaving ? <span className="inline-spinner" aria-hidden="true" /> : null}
            {t('settings.save')}
          </button>
        </div>

        {testResult ? (
          <div className={`inline-message ${testResultType}`}>{testResult}</div>
        ) : null}

        {saveMessage ? (
          <div className={`inline-message ${saveMessage === t('settings.saved') ? 'success' : 'error'}`}>
            {saveMessage}
          </div>
        ) : null}
      </div>
    </section>
  )
}
