import { useState } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { MonthPicker } from '../../components/MonthPicker'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { currentMonth } from '../../lib/month'
import { CategoryTrends } from './CategoryTrends'
import { NetWorthCard } from './NetWorthCard'
import { PortfolioSummaryCard } from './PortfolioSummaryCard'
import { useTrend } from './queries'
import { SummaryTiles } from './SummaryTiles'
import { TrendChart } from './TrendChart'

const h2 = 'text-sm font-medium text-muted'
const WINDOWS = [3, 6, 12]

export function SummaryPage() {
  const [month, setMonth] = useState(currentMonth())
  const [months, setMonths] = useState(6)
  const { data, error, isLoading } = useTrend(month, months)
  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{pl.summary.title}</h1>
      <NetWorthCard />
      <PortfolioSummaryCard />
      <section className="space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{pl.summary.monthHistory}</h2>
          <div className="flex items-center gap-2">
            <Select variant="ghost" aria-label={pl.summary.window} value={months} onChange={(e) => setMonths(Number(e.target.value))}>
              {WINDOWS.map((n) => (
                <option key={n} value={n}>
                  {pl.summary.windowOption(n)}
                </option>
              ))}
            </Select>
            <MonthPicker value={month} onChange={setMonth} max={currentMonth()} />
          </div>
        </header>
        {isLoading && <Spinner />}
        {error && <ErrorMessage message={pl.summary.trendError} />}
        {data && (
          <>
            <SummaryTiles trend={data} />
            <TrendChart trend={data} />
            <CategoryTrends trend={data} />
          </>
        )}
      </section>
    </>
  )
}
