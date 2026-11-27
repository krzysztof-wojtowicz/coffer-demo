import { cn } from '../../lib/cn'

const tones = {
  accent: 'bg-accent',
  positive: 'bg-positive',
  warning: 'bg-warning',
  negative: 'bg-negative',
}

export function Bar({
  pct,
  tone = 'accent',
  label,
  role = 'meter',
}: {
  pct: number
  tone?: keyof typeof tones
  label: string
  role?: 'meter' | 'progressbar'
}) {
  // Width is clamped for display only; aria-valuenow keeps the real value.
  const width = Math.min(100, Math.max(0, pct))
  return (
    <div
      role={role}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      className="h-1.5 overflow-hidden rounded-sm bg-surface-2"
    >
      <div className={cn('h-full rounded-sm', tones[tone])} style={{ width: `${width}%` }} />
    </div>
  )
}
