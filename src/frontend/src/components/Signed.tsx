import { formatMoney, formatPct, signOf } from '../lib/format'
import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

// Sign-coloured amount or percentage. `invert` is for figures where an
// increase is bad (e.g. spending), so positive turns red and negative green.
export function Signed({
  value,
  kind = 'money',
  currency,
  invert = false,
  signed = false,
  prefix,
}: {
  value: string
  kind?: 'money' | 'pct'
  currency?: string
  invert?: boolean
  /** Adds "+" to positive money (percentages always get it). */
  signed?: boolean
  /** Rendered inside the coloured span, e.g. a trend arrow. */
  prefix?: ReactNode
}) {
  const sign = signOf(value)
  const good = invert ? -sign : sign
  const text =
    kind === 'pct' ? formatPct(value, { signed: true }) : (signed && sign > 0 ? '+' : '') + formatMoney(value, currency)
  return (
    <span className={cn('font-mono tabular-nums', good > 0 && 'text-positive', good < 0 && 'text-negative')}>
      {prefix}
      {text}
    </span>
  )
}
