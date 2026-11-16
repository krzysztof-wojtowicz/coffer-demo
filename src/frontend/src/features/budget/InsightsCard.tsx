import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { formatMoney } from '../../lib/money'
import { useInsights } from './queries'

const t = pl.summary

function Change({ change, pct }: { change: string; pct: string | null }) {
  const n = Number(change)
  const up = n > 0
  const down = n < 0
  return (
    <span className={cn('tabular-nums', up && 'text-warning', down && 'text-positive')}>
      <span aria-hidden="true">{up ? '▲ ' : down ? '▼ ' : ''}</span>
      {up ? '+' : ''}
      {formatMoney(change)}
      <span className="ml-2 text-xs">
        {pct === null ? '—' : `${up ? '+' : ''}${pct.replace('.', ',')}%`}
      </span>
    </span>
  )
}

export function LimitBar({
  name,
  spent,
  limit,
  usedPct,
  exceeded,
  over,
}: {
  name: string
  spent: string
  limit: string
  usedPct: string
  exceeded: boolean
  over?: string
}) {
  const pct = Number(usedPct)
  return (
    <li>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{name}</span>
        <span className="flex items-center gap-2 tabular-nums">
          <span className="text-muted">{t.limitUsed(formatMoney(spent), formatMoney(limit))}</span>
          {exceeded && over && <Badge tone="danger">{t.limitExceeded(formatMoney(over))}</Badge>}
        </span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-surface-2">
        <div
          role="progressbar"
          aria-label={name}
          aria-valuenow={Math.round(pct)}
          aria-valuemin={0}
          aria-valuemax={100}
          className={cn('h-2 rounded-full', exceeded ? 'bg-negative' : pct >= 80 ? 'bg-warning' : 'bg-accent')}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </li>
  )
}

export function InsightsCard({ month }: { month: string }) {
  const { data, error, isLoading } = useInsights(month)
  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorMessage message={t.insightsError} />
  return (
    <Card title={t.insightsTitle}>
      {data.comparison.length === 0 ? (
        <p className="text-muted">{t.insightsEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">{t.insightsTitle}</caption>
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th scope="col" className="py-2 pr-3 font-medium">{t.category}</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">{t.colThisMonth} ({month})</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">{t.colPrevMonth} ({data.previous_month})</th>
                <th scope="col" className="py-2 text-right font-medium">{t.colChange}</th>
              </tr>
            </thead>
            <tbody>
              {data.comparison.map((c) => (
                <tr key={c.category_id} className="border-b border-border/60">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{c.category_name}</th>
                  <td className="py-2 pr-3 text-right tabular-nums"><Money value={c.current} /></td>
                  <td className="py-2 pr-3 text-right tabular-nums"><Money value={c.previous} /></td>
                  <td className="py-2 text-right"><Change change={c.change} pct={c.change_pct} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="mt-5 text-sm font-semibold text-text">{t.topGrowthTitle}</h3>
      {data.top_growth.length === 0 ? (
        <p className="mt-1 text-sm text-muted">{t.topGrowthEmpty}</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {data.top_growth.slice(0, 3).map((g) => (
            <li key={g.category_id} className="flex flex-wrap justify-between gap-2 text-sm">
              <span>{g.category_name}</span>
              <span className="tabular-nums text-warning">
                <span aria-hidden="true">▲ </span>
                {t.aboveAverage(formatMoney(g.increase))}
                {g.increase_pct !== null && ` (+${g.increase_pct.replace('.', ',')}%)`}
              </span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-5 text-sm font-semibold text-text">{t.limitsTitle}</h3>
      {data.limits.length === 0 ? (
        <p className="mt-1 text-sm text-muted">{t.limitsEmpty}</p>
      ) : (
        <ul className="mt-2 space-y-3">
          {data.limits.map((l) => (
            <LimitBar
              key={l.category_id}
              name={l.category_name}
              spent={l.spent}
              limit={l.limit}
              usedPct={l.used_pct}
              exceeded={l.exceeded}
              over={String(Math.abs(Number(l.remaining)).toFixed(2))}
            />
          ))}
        </ul>
      )}
    </Card>
  )
}
