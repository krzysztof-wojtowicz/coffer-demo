import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { formatMoney } from '../../lib/money'
import { apiErrorMessage } from '../../lib/errors'
import { useBudget } from './queries'

export function SummaryTiles({ month }: { month: string }) {
  const { data, error, isLoading } = useBudget(month)
  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage message={apiErrorMessage(error)} />
  if (!data) return null
  // Balans = balance of all transactions in the month (no client-side math).
  const s = data.balance.trim()
  const balanceTone = /^-/.test(s) && !/^-[0\s.,]*$/.test(s)
    ? 'text-negative'
    : /^[+]?[0\s.,]*$/.test(s)
      ? ''
      : 'text-positive'
  const tiles = [
    ['income', pl.summary.income, data.income, ''],
    ['expenses', pl.summary.expenses, data.expenses, ''],
    ['balance', pl.summary.balance, data.balance, balanceTone],
  ] as const
  // Tylko do szerokości paska; wyświetlane są wyłącznie stringi z API.
  const total = Math.abs(Number(data.expenses)) || 0
  const share = (v: string) => (total > 0 ? Math.min(100, (Math.abs(Number(v)) / total) * 100) : 0)
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {tiles.map(([key, label, value, tone]) => (
          <Card key={key}>
            <div className="text-sm text-muted">{label}</div>
            <div data-testid={`tile-${key}`} className={`mt-1 text-2xl font-semibold ${tone}`}>
              <span className={tone}>{formatMoney(value)}</span>
            </div>
          </Card>
        ))}
      </div>
      <Card title={pl.summary.byCategory}>
        {data.by_category.length === 0 ? (
          <p className="text-muted">{pl.summary.noExpenses}</p>
        ) : (
          <ul className="space-y-3">
            {data.by_category.map((c) => (
              <li key={c.category_id}>
                <div className="flex justify-between text-sm">
                  <span>{c.category_name}</span>
                  <Money value={c.expenses} />
                </div>
                <div className="mt-1 h-2 rounded-full bg-surface-2">
                  <div
                    className="h-2 rounded-full bg-accent"
                    style={{ width: `${share(c.expenses)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
