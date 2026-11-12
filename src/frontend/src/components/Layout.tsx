import { NavLink, Outlet } from 'react-router-dom'
import { useLogout } from '../features/auth/queries'
import { pl } from '../i18n/pl'
import { cn } from '../lib/cn'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'
import { Button } from './ui/Button'

const links = [
  { to: '/', label: pl.nav.summary, end: true },
  { to: '/transactions', label: pl.nav.transactions, end: false },
  { to: '/portfolio', label: pl.nav.portfolio, end: false },
  { to: '/assistant', label: pl.nav.assistant, end: false },
  { to: '/account', label: pl.nav.account, end: false },
]

export function Layout({ email }: { email: string }) {
  const logout = useLogout()
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-accent/40 bg-surface text-text shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-x-4 px-4 py-3">
          <span className="flex shrink-0 items-center gap-2">
            <Logo />
            <strong className="text-lg tracking-tight text-accent">{pl.appName}</strong>
          </span>
          <nav className="flex min-w-0 flex-1 gap-1 overflow-x-auto whitespace-nowrap">
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
          <div className="flex shrink-0 items-center gap-3">
            <ThemeToggle />
            <span className="hidden max-w-[12rem] truncate text-sm text-muted sm:inline">{email}</span>
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
