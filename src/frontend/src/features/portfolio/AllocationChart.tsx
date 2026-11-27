import { pl } from '../../i18n/pl'
import { formatMoney, formatPct } from '../../lib/format'
import { ASSET_CLASSES } from './queries'

type Slice = { asset_class: string; value: string; share_pct: string }

const R = 40
const C = 2 * Math.PI * R
const GAP = 1.5 // visual gap between segments, in circumference units

// Colour follows the asset-class order (7 classes, chart-1..7), not row position.
const colorOf = (cls: string) => `var(--color-chart-${Math.max(0, ASSET_CLASSES.indexOf(cls as never)) + 1})`

export function AllocationChart({ allocation, compact = false }: { allocation: Slice[]; compact?: boolean }) {
  if (allocation.length === 0) return null
  const name = (cls: string) => pl.portfolio.classes[cls] ?? cls
  const label = `${pl.portfolio.allocation}: ${allocation.map((a) => `${name(a.asset_class)} ${formatPct(a.share_pct)}`).join(', ')}`
  const largest = allocation.reduce((m, a) => (Number(a.share_pct) > Number(m.share_pct) ? a : m), allocation[0])
  let offset = 0
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-6">
      <svg viewBox="0 0 100 100" role="img" aria-label={label} className={compact ? 'size-28 shrink-0' : 'size-40 shrink-0'}>
        <g transform="rotate(-90 50 50)" fill="none" strokeWidth="12">
          {allocation.map((a) => {
            const len = (Number(a.share_pct) / 100) * C
            const gap = allocation.length > 1 ? GAP : 0
            const seg = (
              <circle
                key={a.asset_class}
                cx="50"
                cy="50"
                r={R}
                strokeDasharray={`${Math.max(0, len - gap)} ${C - Math.max(0, len - gap)}`}
                strokeDashoffset={-offset}
                style={{ stroke: colorOf(a.asset_class) }}
              />
            )
            offset += len
            return seg
          })}
        </g>
        <text x="50" y="50" textAnchor="middle" dominantBaseline="central" className="fill-text text-[14px] font-semibold">
          {formatPct(largest.share_pct)}
        </text>
      </svg>
      <ul className="w-full space-y-2 text-sm">
        {allocation.map((a) => (
          <li key={a.asset_class} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: colorOf(a.asset_class) }} />
            <span className="flex-1">{name(a.asset_class)}</span>
            <span className="tabular-nums text-muted">{formatPct(a.share_pct)}</span>
            {!compact && <span className="tabular-nums">{formatMoney(a.value)}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
