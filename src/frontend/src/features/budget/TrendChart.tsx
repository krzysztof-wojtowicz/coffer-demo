import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import { formatMoney } from '../../lib/format'
import type { Trend } from './queries'

const t = pl.summary
const H = 120
/** Drawing width fits 12 months; shorter windows spread out so bars keep one size. */
const WIDTH = 12 * 40
const BAR = 14
const label = (m: string) => `${m.slice(5)}.${m.slice(2, 4)}`

/** Income/expense column pairs per month. Heights are geometry only; amounts shown come from the API strings. */
export function TrendChart({ trend }: { trend: Trend }) {
  const pts = trend.months
  const max = Math.max(0, ...pts.flatMap((p) => [Math.abs(Number(p.income)), Math.abs(Number(p.expenses))]))
  const h = (v: string) => (max > 0 ? (Math.abs(Number(v)) / max) * H : 0)
  const maxLabel = pts
    .flatMap((p) => [p.income, p.expenses])
    .reduce((a, v) => (Math.abs(Number(v)) > Math.abs(Number(a)) ? v : a), '0.00')
  const width = WIDTH
  const slot = WIDTH / Math.max(pts.length, 1)
  return (
    <Card title={t.trendTitle}>
      <svg viewBox={`0 0 ${width} ${H + 20}`} className="w-full" role="img" aria-label={t.trendTitle}>
        <line x1="0" x2={width} y1={H} y2={H} className="stroke-border" strokeWidth="1" />
        {pts.map((p, i) => {
          const x = i * slot + (slot - 2 * BAR - 2) / 2
          const selected = p.month === trend.month
          return (
            <g key={p.month} opacity={selected ? 1 : 0.55} data-selected={selected || undefined}>
              <rect x={x} y={H - h(p.income)} width={BAR} height={h(p.income)} className="fill-positive" />
              <rect x={x + BAR + 2} y={H - h(p.expenses)} width={BAR} height={h(p.expenses)} className="fill-negative" />
              <text
                x={i * slot + slot / 2}
                y={H + 14}
                textAnchor="middle"
                fontSize="9"
                className={selected ? 'fill-text font-semibold' : 'fill-muted'}
              >
                {label(p.month)}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="mt-1 flex flex-wrap items-center gap-4 text-xs text-muted">
        <span className="flex items-center gap-1"><span aria-hidden className="h-2 w-2 rounded-sm bg-positive" />{t.income}</span>
        <span className="flex items-center gap-1"><span aria-hidden className="h-2 w-2 rounded-sm bg-negative" />{t.expenses}</span>
        <span className="ml-auto">{t.chartMax} {formatMoney(maxLabel)}</span>
      </div>
      <table className="sr-only">
        <caption>{t.trendTitle}</caption>
        <thead>
          <tr>
            <th scope="col">{t.colMonth}</th>
            <th scope="col">{t.income}</th>
            <th scope="col">{t.expenses}</th>
          </tr>
        </thead>
        <tbody>
          {pts.map((p) => (
            <tr key={p.month} aria-current={p.month === trend.month ? 'true' : undefined}>
              <th scope="row">{p.month}</th>
              <td>{formatMoney(p.income)}</td>
              <td>{formatMoney(p.expenses)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
