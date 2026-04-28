import { Eye, EyeOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, configureApi, getApiConfig, getDeviceId } from '../services/api'
import { loadGoogleFont } from '../i18n'

const LANGUAGE_OPTIONS = [
  { code: 'en', labelKey: 'settings.languageNames.en' },
  { code: 'kn', labelKey: 'settings.languageNames.kn' },
  { code: 'hi', labelKey: 'settings.languageNames.hi' },
  { code: 'te', labelKey: 'settings.languageNames.te' },
]

export default function Settings() {
  const { t, i18n } = useTranslation()
  const [apiUrl, setApiUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [deviceId, setDeviceId] = useState('')
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
    setDeviceId(getDeviceId())
    setLanguage(storedLanguage)
  }, [i18n.resolvedLanguage])

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
      localStorage.setItem('fs_device_id', deviceId)
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

        <div className="form-field">
          <label className="field-label" htmlFor="device-id">
            {t('settings.deviceId')}
          </label>
          <input
            id="device-id"
            className="field-input"
            type="text"
            value={deviceId}
            onChange={(event) => setDeviceId(event.target.value)}
          />
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
