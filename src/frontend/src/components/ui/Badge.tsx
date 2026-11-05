import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

const tones = {
  neutral: 'bg-surface-2 text-text',
  success: 'bg-accent-soft text-positive',
  warning: 'bg-warning/15 text-warning',
  danger: 'bg-negative/15 text-negative',
  info: 'bg-info/15 text-info',
}

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: keyof typeof tones
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
