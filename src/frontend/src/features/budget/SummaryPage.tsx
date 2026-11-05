import { useState } from 'react'
import { MonthPicker } from '../../components/MonthPicker'
import { pl } from '../../i18n/pl'
import { currentMonth } from '../../lib/month'
import { AssistantPanel } from '../assistant/AssistantPanel'
import { SummaryTiles } from './SummaryTiles'
import { useBudget } from './queries'

export function SummaryPage() {
  const [month, setMonth] = useState(currentMonth())
  const { data } = useBudget(month)
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-text">{pl.summary.title}</h1>
        <MonthPicker value={month} onChange={setMonth} max={currentMonth()} />
      </div>
      <SummaryTiles month={month} />
      {data && <AssistantPanel month={month} summary={data} />}
    </>
  )
}
