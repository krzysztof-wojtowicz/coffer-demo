import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { BarList } from '../../components/ui/BarList'
import { Card } from '../../components/ui/Card'
import { Stat } from '../../components/ui/Stat'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { useBudget } from './queries'

export function SummaryTiles({ month }: { month: string }) {
  const { data, error, isLoading } = useBudget(month)
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage message={apiErrorMessage(error)} />
  if (!data) return null
  // Tylko do szerokości paska; wyświetlane są wyłącznie stringi z API.
  const total = Math.abs(Number(data.expenses)) || 0
  const share = (v: string) => (total > 0 ? Math.min(100, (Math.abs(Number(v)) / total) * 100) : 0)
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <Stat label={pl.summary.income} value={<Money value={data.income} />} testId="tile-income" />
        </Card>
        <Card>
          <Stat label={pl.summary.expenses} value={<Money value={data.expenses} />} testId="tile-expenses" />
        </Card>
        <Card>
          {/* Balance = balance of all transactions in the month (no client-side math). */}
          <Stat label={pl.summary.balance} value={<Signed value={data.balance} />} testId="tile-balance" />
        </Card>
      </div>
      <Card title={pl.summary.byCategory}>
        {data.by_category.length === 0 ? (
          <p className="text-muted">{pl.summary.noExpenses}</p>
        ) : (
          <BarList
            role="meter"
            items={data.by_category.map((c) => ({
              key: String(c.category_id),
              label: c.category_name,
              value: <Money value={c.expenses} />,
              pct: share(c.expenses),
            }))}
          />
        )}
      </Card>
    </>
  )
}
