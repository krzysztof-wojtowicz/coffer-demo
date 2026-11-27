import { Link } from 'react-router-dom'
import { AllocationChart, targetSlices } from '../portfolio/AllocationChart'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Card } from '../../components/ui/Card'
import { Stat } from '../../components/ui/Stat'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { formatPct } from '../../lib/format'
import { formatAsOf, usePortfolioSummary } from '../portfolio/queries'

const TOP_N = 5

export function PortfolioSummaryCard() {
  const { data, error, isLoading } = usePortfolioSummary()
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage message={apiErrorMessage(error)} />
  if (!data) return null
  const linkCls = 'text-sm font-medium text-accent hover:underline'
  // Profile but nothing valued yet: show the target alone, without a comparison.
  const targetOnly = data.target ? (
    <div className="mt-4">
      <div className="mb-2 text-sm text-muted">{pl.profile.targetTitle}</div>
      <AllocationChart
        compact
        targetOnly
        allocation={targetSlices(data.target.classes.map((c) => ({ asset_class: c.asset_class, share_pct: c.target_pct })))}
      />
    </div>
  ) : null
  if (data.holdings.length === 0) {
    return (
      <Card title={pl.summary.portfolioTitle}>
        <p className="text-muted">{pl.summary.portfolioEmpty}</p>
        <Link to="/portfolio" className={linkCls}>
          {pl.summary.portfolioAdd}
        </Link>
        {targetOnly}
      </Card>
    )
  }
  const pct = data.total_gain_pct
  const top = [...data.holdings]
    .filter((h) => h.share_pct !== null)
    .sort((a, b) => Number(b.share_pct) - Number(a.share_pct))
    .slice(0, TOP_N)
  return (
    <Card title={pl.summary.portfolioTitle}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label={pl.portfolio.totalValue} value={<Money value={data.total_value} />} />
        <Stat label={pl.summary.portfolioInvested} value={<Money value={data.total_cost} />} />
        <Stat
          label={pl.portfolio.totalGain}
          value={
            <>
              <Signed value={data.total_gain} />
              {pct !== null && (
                <span className="ml-2 text-base">
                  <Signed value={pct} kind="pct" />
                </span>
              )}
            </>
          }
        />
      </div>
      {data.allocation.length === 0 && targetOnly}
      {data.allocation.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-sm text-muted">{pl.portfolio.allocation}</div>
          <AllocationChart allocation={data.allocation} target={data.target ?? null} compact />
        </div>
      )}
      {top.length > 0 && (
        <div className="mt-4">
          <div className="text-sm text-muted">{pl.summary.portfolioTop}</div>
          <ul className="mt-2 space-y-1">
            {top.map((h) => (
              <li key={h.id} className="flex justify-between gap-3 text-sm">
                <span>
                  {h.name} <span className="text-muted">({pl.assetClass[h.asset_class]})</span>
                </span>
                <span className="flex gap-3 tabular-nums">
                  <span className="text-muted">{formatPct(h.share_pct)}</span>
                  <Signed value={h.gain} />
                  {h.gain_pct !== null && <Signed value={h.gain_pct} kind="pct" />}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.prices_as_of && (
        <p className="mt-4 text-xs text-muted">{pl.portfolio.pricesAsOf(formatAsOf(data.prices_as_of))}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-4">
        <Link to="/portfolio" className={linkCls}>
          {pl.summary.portfolioDetails}
        </Link>
      </div>
    </Card>
  )
}
