import { Link, Outlet, useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { useAuth } from '@/features/auth/useAuth'

interface NavItem {
  to: string
  label: string
  managerOnly?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Home' },
  { to: '/dockets', label: 'Dockets' },
  { to: '/team', label: 'Team', managerOnly: true },
]

function isNavActive(itemPath: string, pathname: string): boolean {
  if (itemPath === '/') return pathname === '/'
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`)
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()

  const items = NAV.filter((item) => !item.managerOnly || user?.is_manager)

  return (
    <div className="shell">
      <header className="shell__header">
        <div className="shell__header-inner">
          <div className="shell__brand">
            <span className="shell__brand-name">Moriarty Group</span>
            <span className="shell__brand-sub">
              SuperValu · {user?.store?.name ?? 'All stores'}
            </span>
          </div>

          <div className="shell__user">
            <div className="shell__user-meta">
              <div className="shell__user-name">{user?.full_name || user?.email}</div>
              <div className="shell__user-sub">{user?.role}</div>
            </div>
            <Button
              variant="on-brand"
              size="sm"
              onClick={logout}
              icon={<span aria-hidden="true">⏻</span>}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <nav className="shell__nav" aria-label="Main">
        <div className="shell__nav-inner">
          {items.map((item) => {
            const active = isNavActive(item.to, pathname)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={active ? 'active' : undefined}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            )
          })}
        </div>
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  )
}
