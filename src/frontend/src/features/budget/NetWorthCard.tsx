import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Card } from '../../components/ui/Card'
import { Stat } from '../../components/ui/Stat'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { useNetWorth } from './queries'

export function NetWorthCard() {
  const { data, error, isLoading } = useNetWorth()
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage message={apiErrorMessage(error)} />
  if (!data) return null
  return (
    <Card title={pl.summary.netWorthTitle}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label={pl.summary.netWorthCash} value={<Money value={data.cash_balance} />} />
        <Stat label={pl.summary.netWorthPortfolio} value={<Money value={data.portfolio_value} />} />
        <div className="rounded-md bg-surface-2 p-3">
          <Stat label={pl.summary.netWorthTotal} value={<Money value={data.net_worth} />} testId="net-worth-total" />
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        {pl.summary.netWorthAsOf} {data.as_of}
      </p>
      {!data.opening_balance_set && (
        <p className="mt-1 text-xs text-muted">
          {pl.summary.netWorthSetBalance}{' '}
          <Link className="text-accent hover:underline" to="/account">
            {pl.summary.netWorthSetBalanceLink}
          </Link>
        </p>
      )}
      {!data.portfolio_complete && (
        <p className="mt-1 text-xs text-muted">{pl.summary.netWorthIncomplete}</p>
      )}
    </Card>
  )
}
