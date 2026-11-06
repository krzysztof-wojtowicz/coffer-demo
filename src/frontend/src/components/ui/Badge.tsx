import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

const tones = {
  neutral: 'bg-surface-2 text-text',
  success: 'bg-positive/8 text-positive',
  warning: 'bg-warning/8 text-warning',
  danger: 'bg-negative/8 text-negative',
  info: 'bg-info/8 text-info',
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
