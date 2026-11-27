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
    <section className={cn('rounded-md bg-linear-to-b from-surface to-surface/60 p-5 shadow-[inset_0_1px_0_rgb(255_255_255/0.04),0_8px_24px_rgb(0_0_0/0.25)]', className)}>
      {(title || actions) && (
        <header className="mb-4 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-medium text-muted">{title}</h2>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
