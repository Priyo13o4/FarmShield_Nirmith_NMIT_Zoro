import { Outlet } from 'react-router-dom'

import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function AppLayout({ showSetupBanner, setupBannerText }) {
  return (
    <div className="app-shell">
      <Sidebar />

      <div className="main-shell">
        <TopBar />
        <main className="content-scroll">
          {showSetupBanner ? <div className="setup-banner">{setupBannerText}</div> : null}
          <Outlet />
        </main>
      </div>
    </div>
  )
}
