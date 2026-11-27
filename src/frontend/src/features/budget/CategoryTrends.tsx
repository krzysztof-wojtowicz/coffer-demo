import { useState } from 'react'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import { formatPct, signOf } from '../../lib/format'
import type { Trend } from './queries'

const t = pl.summary
const TOP = 8
const W = 80
const H = 24

/** Flat baseline when every point is zero, so we never divide by a zero max. */
function Sparkline({ values }: { values: string[] }) {
  const nums = values.map((v) => Math.abs(Number(v)))
  const max = Math.max(0, ...nums)
  const step = nums.length > 1 ? W / (nums.length - 1) : 0
  const pts = nums.map((n, i) => [i * step, max > 0 ? H - 2 - (n / max) * (H - 4) : H - 2] as const)
  const last = pts[pts.length - 1]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-6 w-20" aria-hidden="true">
      <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" className="stroke-muted" strokeWidth="1.5" />
      {last && <circle cx={last[0]} cy={last[1]} r="2.5" className="fill-accent" />}
    </svg>
  )
}

export function CategoryTrends({ trend }: { trend: Trend }) {
  const [all, setAll] = useState(false)
  const cats = trend.categories
  const shown = all ? cats : cats.slice(0, TOP)
  return (
    <Card title={t.categoryTrendsTitle}>
      {cats.every((c) => signOf(c.amounts[c.amounts.length - 1] ?? '0') === 0) ? (
        <p className="text-muted">{t.noExpenses}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">{t.categoryTrendsTitle}</caption>
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th scope="col" className="py-2 pr-3 font-medium">{t.category}</th>
                  <th scope="col" className="py-2 pr-3 font-medium">{t.colTrend}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{t.colThisMonth}</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">{t.colAverage}</th>
                  <th scope="col" className="py-2 text-right font-medium">{t.colChange}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((c) => {
                  const now = c.amounts[c.amounts.length - 1] ?? '0.00'
                  const sign = c.change === null ? 0 : signOf(c.change)
                  return (
                    <tr key={c.category_id} className="border-b border-border/60">
                      <th scope="row" className="py-2 pr-3 text-left font-normal">{c.category_name}</th>
                      <td className="py-2 pr-3"><Sparkline values={c.amounts} /></td>
                      <td className="py-2 pr-3 text-right"><Money value={now} /></td>
                      <td className="py-2 pr-3 text-right">{c.average === null ? t.noData : <Money value={c.average} />}</td>
                      <td className="py-2 text-right tabular-nums">
                        {c.change === null ? (
                          t.noData
                        ) : (
                          <>
                            <Signed
                              value={c.change}
                              invert
                              signed
                              prefix={<span aria-hidden="true">{sign > 0 ? '▲ ' : sign < 0 ? '▼ ' : ''}</span>}
                            />
                            <span className="ml-2 text-xs">
                              {c.change_pct === null ? formatPct(null) : <Signed value={c.change_pct} kind="pct" invert />}
                            </span>
                          </>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {cats.length > TOP && (
            <Button type="button" variant="ghost" className="mt-3" onClick={() => setAll((v) => !v)}>
              {all ? t.showLess : t.showAll}
            </Button>
          )}
        </>
      )}
    </Card>
  )
}
