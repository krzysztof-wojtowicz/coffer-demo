import { NavLink, Outlet } from 'react-router-dom'
import { useLogout } from '../features/auth/queries'
import { pl } from '../i18n/pl'
import { cn } from '../lib/cn'
import { Button } from './ui/Button'

const links = [
  { to: '/', label: pl.nav.summary, end: true },
  { to: '/transactions', label: pl.nav.transactions, end: false },
  { to: '/import', label: pl.nav.import, end: false },
  { to: '/portfolio', label: pl.nav.portfolio, end: false },
  { to: '/assistant', label: pl.nav.assistant, end: false },
  { to: '/profile', label: pl.nav.profile, end: false },
  { to: '/account', label: pl.nav.account, end: false },
]

export function Layout({ email }: { email: string }) {
  const logout = useLogout()
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-border bg-surface text-text">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <strong className="text-lg tracking-tight">{pl.appName}</strong>
          <nav className="flex flex-wrap gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm',
                    isActive ? 'bg-accent-soft font-semibold text-accent' : 'text-muted hover:bg-surface-2 hover:text-text',
                  )
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-muted">{email}</span>
            <Button variant="secondary" size="sm" onClick={() => logout.mutate()}>
              {pl.nav.logout}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-4 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
