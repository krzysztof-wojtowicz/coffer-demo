import type { ReactNode } from 'react'

export function Stat({
  label,
  value,
  delta,
  testId,
}: {
  label: ReactNode
  value: ReactNode
  delta?: ReactNode
  testId?: string
}) {
  return (
    <div>
      <div className="text-sm text-muted">{label}</div>
      <div data-testid={testId} className="font-mono text-xl font-semibold tabular-nums">{value}</div>
      {delta && <div className="text-sm">{delta}</div>}
    </div>
  )
}
