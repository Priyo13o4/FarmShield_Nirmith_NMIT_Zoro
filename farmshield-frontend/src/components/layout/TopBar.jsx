import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useFarm } from '../../context/FarmContext'

const PATH_TITLE_KEY = {
  '/': 'nav.dashboard',
  '/history': 'nav.history',
  '/alerts': 'nav.alerts',
  '/controls': 'nav.controls',
  '/settings': 'nav.settings',
}

const LANGUAGE_OPTIONS = ['en', 'kn', 'hi', 'te']

function getRelativeTimeLabel(lastUpdated, t) {
  if (!lastUpdated) {
    return t('common.never')
  }

  const now = Date.now()
  const updatedAt = new Date(lastUpdated).getTime()
  const diffMinutes = Math.max(Math.floor((now - updatedAt) / 60000), 0)

  if (diffMinutes < 1) {
    return t('common.justNow')
  }
  if (diffMinutes < 60) {
    return t('common.minutesAgo', { count: diffMinutes })
  }

  return t('common.hoursAgo', { count: Math.floor(diffMinutes / 60) })
}

export default function TopBar() {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const { lastUpdated } = useFarm()
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setTick((current) => current + 1)
    }, 60000)

    return () => {
      clearInterval(timer)
    }
  }, [])

  const title = t(PATH_TITLE_KEY[pathname] || 'nav.dashboard')

  const relativeTime = useMemo(
    () => getRelativeTimeLabel(lastUpdated, t),
    [lastUpdated, t, tick]
  )

  return (
    <header className="topbar">
      <h1 className="topbar-title">{title}</h1>

      <div className="topbar-meta">
        <span className="relative-time">
          {t('common.lastUpdated')} {relativeTime}
        </span>

        <div className="lang-switch" role="group" aria-label={t('settings.language')}>
          {LANGUAGE_OPTIONS.map((languageCode) => (
            <button
              key={languageCode}
              type="button"
              className={`lang-btn${i18n.resolvedLanguage === languageCode ? ' active' : ''}`}
              onClick={() => i18n.changeLanguage(languageCode)}
              aria-label={t(`settings.languageNames.${languageCode}`)}
            >
              {t(`settings.languageShort.${languageCode}`)}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
