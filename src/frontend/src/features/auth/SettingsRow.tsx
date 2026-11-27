import type { ReactNode } from 'react'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { Button } from '../../components/ui/Button'

/** A settings line showing a label and its current value; opens its form in place. Escape closes it. */
export function SettingsRow({
  label,
  value,
  open,
  onToggle,
  danger = false,
  children,
}: {
  label: string
  value?: ReactNode
  open: boolean
  onToggle: () => void
  danger?: boolean
  children: ReactNode
}) {
  return (
    <div
      className="border-t border-border first:border-t-0"
      onKeyDown={(e) => {
        if (e.key === 'Escape' && open) onToggle()
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center gap-4 rounded px-1 py-3 text-left text-sm transition-colors hover:bg-surface-2/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span className={cn('w-40 shrink-0 font-medium', danger && 'text-negative')}>{label}</span>
        <span className="min-w-0 flex-1 truncate text-muted">{value}</span>
        <svg
          aria-hidden
          viewBox="0 0 20 20"
          className={cn('size-4 shrink-0 text-muted transition-transform', open && 'rotate-90')}
          fill="currentColor"
        >
          <path d="M7.5 5.5 12 10l-4.5 4.5-1-1L10 10 6.5 6.5z" />
        </svg>
      </button>
      {open && (
        <div className="px-1 pb-4">
          {children}
          <Button variant="ghost" size="sm" className="mt-3" onClick={onToggle}>
            {pl.common.cancel}
          </Button>
        </div>
      )}
    </div>
  )
}
