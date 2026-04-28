import {
  Bell,
  Gauge,
  History,
  MessageSquare,
  Settings,
  SlidersHorizontal,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useFarm } from '../../context/FarmContext'

const NAV_ITEMS = [
  { path: '/', labelKey: 'nav.dashboard', icon: Gauge },
  { path: '/history', labelKey: 'nav.history', icon: History },
  { path: '/alerts', labelKey: 'nav.alerts', icon: Bell },
  { path: '/chat', labelKey: 'nav.chat', icon: MessageSquare },
  { path: '/controls', labelKey: 'nav.controls', icon: SlidersHorizontal },
  { path: '/settings', labelKey: 'nav.settings', icon: Settings },
]

function FarmShieldLogo() {
  return (
    <svg
      viewBox="0 0 32 32"
      className="brand-mark"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M16 2L27 7V14C27 21.5 22.2 27.5 16 30C9.8 27.5 5 21.5 5 14V7L16 2Z"
        fill="var(--color-primary)"
      />
      <path
        d="M15 10C12.5 10.7 10.8 13.2 11.1 15.8C11.3 18.4 13.2 20.6 15.7 21.2C15.9 18.9 16.2 16.4 17.4 14.2C18.5 12.2 20.3 10.7 22.5 9.8C20.4 9.4 17.8 9.3 15 10Z"
        fill="var(--color-healthy)"
      />
      <path
        d="M14.8 20.8C14.8 17.8 16 15.1 18.2 13.2"
        stroke="var(--color-surface-0)"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}

export default function Sidebar() {
  const { t } = useTranslation()
  const { unreadAlertCount, connectionStatus } = useFarm()

  return (
    <aside className="sidebar" aria-label={t('app.brand')}>
      <div className="brand">
        <FarmShieldLogo />
        <span className="brand-name">{t('app.brand')}</span>
      </div>

      <nav className="sidebar-nav" aria-label={t('app.primaryNav')}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const showUnreadBadge = item.path === '/alerts' && unreadAlertCount > 0

          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `nav-item${isActive ? ' active' : ''}`
              }
            >
              <span className="nav-item-label">
                <Icon size={18} aria-hidden="true" />
                <span>{t(item.labelKey)}</span>
              </span>
              {showUnreadBadge ? (
                <span className="unread-badge" aria-label={String(unreadAlertCount)}>
                  {unreadAlertCount}
                </span>
              ) : null}
            </NavLink>
          )
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="connection-pill" data-status={connectionStatus}>
          <span className="connection-dot" />
          <span>{t(`status.${connectionStatus}`)}</span>
        </div>
      </div>
    </aside>
  )
}
