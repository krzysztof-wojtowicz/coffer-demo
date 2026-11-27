import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Badge } from '../../components/ui/Badge'
import { BarList } from '../../components/ui/BarList'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { formatMoney, formatPct, signOf } from '../../lib/format'
import { useInsights } from './queries'

const t = pl.summary

function Change({ change, pct }: { change: string; pct: string | null }) {
  const sign = signOf(change)
  return (
    <span className="tabular-nums">
      <Signed
        value={change}
        invert
        signed
        prefix={<span aria-hidden="true">{sign > 0 ? '▲ ' : sign < 0 ? '▼ ' : ''}</span>}
      />
      <span className="ml-2 text-xs">{pct === null ? formatPct(null) : <Signed value={pct} kind="pct" invert />}</span>
    </span>
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
                {g.increase_pct !== null && ` (${formatPct(g.increase_pct, { signed: true })})`}
              </span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-5 text-sm font-semibold text-text">{t.limitsTitle}</h3>
      {data.limits.length === 0 ? (
        <p className="mt-1 text-sm text-muted">{t.limitsEmpty}</p>
      ) : (
        <div className="mt-2">
          <BarList
            role="progressbar"
            items={data.limits.map((l) => ({
              key: String(l.category_id),
              label: l.category_name,
              value: (
                <span className="flex items-center gap-2">
                  <span className="text-muted">{t.limitUsed(formatMoney(l.spent), formatMoney(l.limit))}</span>
                  {l.exceeded && (
                    <Badge tone="danger">{t.limitExceeded(formatMoney(l.remaining.replace(/^-/, '')))}</Badge>
                  )}
                </span>
              ),
              pct: Number(l.used_pct),
              tone: l.exceeded ? 'negative' : Number(l.used_pct) >= 80 ? 'warning' : 'accent',
            }))}
          />
        </div>
      )}
    </Card>
  )
}
