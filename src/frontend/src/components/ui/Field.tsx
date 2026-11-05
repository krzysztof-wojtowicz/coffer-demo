import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export function Field({
  label,
  error,
  children,
  className,
}: {
  label: ReactNode
  error?: string | null
  children: ReactNode
  className?: string
}) {
  return (
    <label className={cn('flex flex-col gap-1 text-sm font-medium text-text', className)}>
      {label}
      {children}
      {error && (
        <span role="alert" className="text-xs font-normal text-negative">
          {error}
        </span>
      )}
    </label>
  )
}
