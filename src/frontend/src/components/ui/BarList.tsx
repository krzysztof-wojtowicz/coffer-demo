import type { ReactNode } from 'react'
import { Bar } from './Bar'

type Tone = Parameters<typeof Bar>[0]['tone']

export function BarList({
  items,
  role,
}: {
  items: { key: string; label: string; value: ReactNode; pct: number; tone?: Tone }[]
  role?: 'meter' | 'progressbar'
}) {
  return (
    <ul className="space-y-3">
      {items.map((i) => (
        <li key={i.key}>
          <div className="mb-1 flex justify-between gap-2 text-sm">
            <span>{i.label}</span>
            <span className="tabular-nums">{i.value}</span>
          </div>
          <Bar pct={i.pct} tone={i.tone} label={i.label} role={role} />
        </li>
      ))}
    </ul>
  )
}
