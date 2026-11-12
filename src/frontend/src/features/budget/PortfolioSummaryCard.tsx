import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { apiErrorMessage } from '../../lib/errors'
import { usePortfolioSummary } from '../portfolio/queries'

const TOP_N = 5

export function PortfolioSummaryCard() {
  const { data, error, isLoading } = usePortfolioSummary()
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage message={apiErrorMessage(error)} />
  if (!data) return null
  const linkCls = 'text-sm font-medium text-accent hover:underline'
  if (data.holdings.length === 0) {
    return (
      <Card title={pl.summary.portfolioTitle}>
        <p className="text-muted">{pl.summary.portfolioEmpty}</p>
        <Link to="/portfolio" className={linkCls}>
          {pl.summary.portfolioAdd}
        </Link>
      </Card>
    )
  }
  const pct = data.total_gain_pct
  const neg = data.total_gain.startsWith('-')
  const top = [...data.holdings]
    .filter((h) => h.share_pct !== null)
    .sort((a, b) => Number(b.share_pct) - Number(a.share_pct))
    .slice(0, TOP_N)
  return (
    <Card title={pl.summary.portfolioTitle}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <div className="text-sm text-muted">{pl.portfolio.totalValue}</div>
          <div className="mt-1 text-2xl font-semibold">
            <Money value={data.total_value} />
          </div>
        </div>
        <div>
          <div className="text-sm text-muted">{pl.summary.portfolioInvested}</div>
          <div className="mt-1 text-2xl font-semibold">
            <Money value={data.total_cost} />
          </div>
        </div>
        <div>
          <div className="text-sm text-muted">{pl.portfolio.totalGain}</div>
          <div className="mt-1 text-2xl font-semibold">
            <Money value={data.total_gain} colored />
            {pct !== null && (
              <span className={cn('ml-2 text-base', neg ? 'text-negative' : 'text-positive')}>
                {neg ? '' : '+'}
                {pct.replace('.', ',')}%
              </span>
            )}
          </div>
        </div>
      </div>
      {data.allocation.length > 0 && (
        <div className="mt-4">
          <div className="text-sm text-muted">{pl.portfolio.allocation}</div>
          <ul className="mt-2 space-y-2">
            {data.allocation.map((a) => (
              <li key={a.asset_class}>
                <div className="flex justify-between gap-3 text-sm">
                  <span>{pl.portfolio.classes[a.asset_class]}</span>
                  <span className="tabular-nums">{a.share_pct.replace('.', ',')}%</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-surface-2" aria-hidden="true">
                  <div
                    className="h-2 rounded-full bg-accent"
                    style={{ width: `${Math.min(100, Number(a.share_pct))}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {top.length > 0 && (
        <div className="mt-4">
          <div className="text-sm text-muted">{pl.summary.portfolioTop}</div>
          <ul className="mt-2 space-y-1">
            {top.map((h) => (
              <li key={h.id} className="flex justify-between gap-3 text-sm">
                <span>
                  {h.name} <span className="text-muted">({pl.portfolio.classes[h.asset_class]})</span>
                </span>
                <span className="flex gap-3 tabular-nums">
                  <span className="text-muted">{(h.share_pct as string).replace('.', ',')}%</span>
                  <Money value={h.gain} colored />
                  {h.gain_pct !== null && (
                    <span className={h.gain.startsWith('-') ? 'text-negative' : 'text-positive'}>
                      {h.gain.startsWith('-') ? '' : '+'}
                      {h.gain_pct.replace('.', ',')}%
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Link to="/portfolio" className={cn(linkCls, 'mt-4 inline-block')}>
        {pl.summary.portfolioDetails}
      </Link>
    </Card>
  )
}
