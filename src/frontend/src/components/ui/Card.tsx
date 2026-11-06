import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export function Card({
  title,
  actions,
  children,
  className,
}: {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('rounded-xl border border-border bg-surface p-5 shadow-[0_1px_2px_rgb(0_0_0/0.12),0_4px_16px_rgb(0_0_0/0.06)]', className)}>
      {(title || actions) && (
        <header className="mb-4 flex items-center justify-between gap-2">
          {title && <h2 className="border-l-2 border-accent pl-2.5 text-base font-semibold tracking-tight text-text">{title}</h2>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
