import { Link } from 'react-router-dom'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { formatMoney, formatPct, signOf } from '../../lib/format'
import { ASSET_CLASSES, type PortfolioSummary } from './queries'

type Slice = { asset_class: string; value: string; share_pct: string }
type Target = PortfolioSummary['target']

/** Target shares drawn as a pie of their own (profile card, or a profile with an empty wallet). */
export const targetSlices = (shares: { asset_class: string; share_pct: string | number }[]): Slice[] =>
  shares.map((t) => ({ asset_class: t.asset_class, value: '0', share_pct: String(t.share_pct) }))

const GAP_WARN_PP = 5
const pp = (v: string) => `${signOf(v) > 0 ? '+' : ''}${v.replace(/\.0+$/, '').replace('.', ',')} pp`

const R = 40
const C = 2 * Math.PI * R
const GAP = 1.5 // visual gap between segments, in circumference units

// Colour follows the asset-class order (7 classes, chart-1..7), not row position.
const colorOf = (cls: string) => `var(--color-chart-${Math.max(0, ASSET_CLASSES.indexOf(cls as never)) + 1})`

/**
 * `target` undefined: plain pie. A target object: legend rows get the target share and gap.
 * `target` null: the user has no profile, so the footer links to the Account page.
 */
export function AllocationChart({
  allocation,
  compact = false,
  target,
  targetOnly = false,
}: {
  allocation: Slice[]
  compact?: boolean
  target?: Target
  /** `allocation` holds target shares (no holdings valued): rows read "cel N%", no comparison. */
  targetOnly?: boolean
}) {
  if (allocation.length === 0) return null
  const name = (cls: string) => pl.assetClass[cls] ?? cls
  const rows = target
    ? [
        ...allocation.map((a) => ({ ...a, t: target.classes.find((c) => c.asset_class === a.asset_class) })),
        ...target.classes
          .filter((c) => !allocation.some((a) => a.asset_class === c.asset_class))
          .map((c) => ({ asset_class: c.asset_class, value: '0', share_pct: c.current_pct, t: c })),
      ]
    : allocation.map((a) => ({ ...a, t: undefined }))
  const label = `${pl.portfolio.allocation}: ${allocation.map((a) => `${name(a.asset_class)} ${formatPct(a.share_pct)}`).join(', ')}`
  const largest = allocation.reduce((m, a) => (Number(a.share_pct) > Number(m.share_pct) ? a : m), allocation[0])
  let offset = 0
  return (
    <div>
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
        {rows.map((a) => (
          <li key={a.asset_class} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: colorOf(a.asset_class) }} />
            <span className="flex-1">{name(a.asset_class)}</span>
            <span className="tabular-nums text-muted">
              {targetOnly ? pl.portfolio.target(formatPct(a.share_pct)) : formatPct(a.share_pct)}
            </span>
            {a.t && (
              <span className="tabular-nums text-muted">
                · {pl.portfolio.target(formatPct(a.t.target_pct))}
                {a.t.gap_pp !== null && (
                  <>
                    {' · '}
                    <span className={cn(Math.abs(Number(a.t.gap_pp)) >= GAP_WARN_PP && 'font-medium text-warning')}>
                      {pp(a.t.gap_pp)}
                    </span>
                  </>
                )}
              </span>
            )}
            {!compact && <span className="tabular-nums">{formatMoney(a.value)}</span>}
          </li>
        ))}
      </ul>
    </div>
    {target && target.total_gap_pp !== null && (
      <p className="mt-3 text-sm text-muted">{pl.portfolio.totalGap(target.total_gap_pp.replace(/\.0+$/, '').replace('.', ','))}</p>
    )}
    {target === null && (
      <Link to="/account" className="mt-3 inline-block text-sm font-medium text-accent hover:underline">
        {pl.profile.setProfile}
      </Link>
    )}
    </div>
  )
}
