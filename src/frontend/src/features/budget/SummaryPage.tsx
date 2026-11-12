import { useState } from 'react'
import { MonthPicker } from '../../components/MonthPicker'
import { pl } from '../../i18n/pl'
import { currentMonth } from '../../lib/month'
import { NetWorthCard } from './NetWorthCard'
import { PortfolioSummaryCard } from './PortfolioSummaryCard'
import { SummaryTiles } from './SummaryTiles'

const h2 = 'border-l-2 border-accent pl-2.5 text-base font-semibold tracking-tight text-text'

export function SummaryPage() {
  const [month, setMonth] = useState(currentMonth())
  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{pl.summary.title}</h1>
      <NetWorthCard />
      <PortfolioSummaryCard />
      <section className="space-y-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{pl.summary.monthHistory}</h2>
          <MonthPicker value={month} onChange={setMonth} max={currentMonth()} />
        </header>
        <SummaryTiles month={month} />
      </section>
    </>
  )
}
