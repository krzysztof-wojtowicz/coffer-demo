import type { ReactNode } from 'react'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Card } from '../../components/ui/Card'
import { Stat } from '../../components/ui/Stat'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { formatPct, signOf } from '../../lib/format'
import type { Trend } from './queries'

const t = pl.summary

type Change = { amount: string }

/** Percentage-point difference, e.g. "−10,0 p.p."; the API value is already rounded. */
function Pp({ value }: { value: string }) {
  const sign = signOf(value)
  const text = value.replace('.', ',').replace('-', '−')
  return (
    <span className={cn('font-mono tabular-nums', sign > 0 && 'text-positive', sign < 0 && 'text-negative')}>
      {sign > 0 ? '+' : ''}
      {text} {t.ppUnit}
    </span>
  )
}

/** Change vs the window average; `invert` for figures where more is worse. */
function Delta({ change, invert, pp }: { change: Change | null | undefined; invert?: boolean; pp?: boolean }) {
  return (
    <span className="text-xs text-muted">
      {change ? (
        <>
          {pp ? <Pp value={change.amount} /> : <Signed value={change.amount} signed invert={invert} />} {t.vsAverage}
        </>
      ) : (
        t.noData
      )}
    </span>
  )
}

function Tile({ label, value, delta, testId }: { label: string; value: ReactNode; delta: ReactNode; testId: string }) {
  return (
    <Card>
      <Stat label={label} value={value} delta={delta} testId={testId} />
    </Card>
  )
}

export function SummaryTiles({ trend }: { trend: Trend }) {
  const last = trend.months[trend.months.length - 1]
  if (!last) return null
  const c = trend.change
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Tile label={t.income} value={<Money value={last.income} />} delta={<Delta change={c?.income} />} testId="tile-income" />
      <Tile
        label={t.expenses}
        value={<Money value={last.expenses} />}
        delta={<Delta change={c?.expenses} invert />}
        testId="tile-expenses"
      />
      <Tile
        label={t.balance}
        value={<Signed value={last.balance} />}
        delta={<Delta change={c?.balance} />}
        testId="tile-balance"
      />
      <Tile
        label={t.savingsRate}
        value={last.savings_rate === null ? formatPct(null) : formatPct(last.savings_rate)}
        delta={<Delta change={c?.savings_rate} pp />}
        testId="tile-savings"
      />
    </div>
  )
}
