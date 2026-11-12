import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { MonthPicker } from '../../components/MonthPicker'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { currentMonth } from '../../lib/month'
import { useBudget } from '../budget/queries'
import { usePortfolioSummary, type AdviceHoldingIn } from '../portfolio/queries'
import { AiPanel } from './AiPanel'
import { RationaleList, formatDateTime, formatSeconds, runTone } from './parts'
import { useRuns, useSuggestions } from './queries'

export function AssistantPage() {
  const a = pl.assistant
  const suggestions = useSuggestions()
  const runs = useRuns()
  const [month, setMonth] = useState(currentMonth())
  const budget = useBudget(month)
  const portfolio = usePortfolioSummary()
  // Not converted to PLN (missing FX rate): the advisor must not treat it as PLN.
  const holdings = (portfolio.data?.holdings ?? []).map(
    (v): AdviceHoldingIn => ({
      symbol: v.symbol,
      asset_class: v.asset_class,
      quantity: v.quantity,
      current_value: v.converted ? v.current_value : null,
    }),
  )
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-text">{pl.nav.assistant}</h1>
        <MonthPicker value={month} onChange={setMonth} max={currentMonth()} />
      </div>
      {budget.isError && <ErrorMessage message={apiErrorMessage(budget.error)} />}
      {(budget.data || budget.isError) && (
        <AiPanel month={month} summary={budget.data ?? null} holdings={holdings} />
      )}
      <Card title={a.historyTitle}>
        {suggestions.isLoading && <p>{pl.common.loading}</p>}
        {suggestions.isError && <ErrorMessage message={pl.common.genericError} />}
        {suggestions.data?.length === 0 && <p className="text-muted">{a.historyEmpty}</p>}
        <div className="space-y-3">
          {suggestions.data?.map((s) => (
            <article key={s.id} className="rounded-md border border-border bg-surface-2 p-3">
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone="info">{a.kind[s.type] ?? s.type}</Badge>
                {formatDateTime(s.generated_at)}
                {s.month && ` · ${a.monthLabel}: ${s.month}`}
              </p>
              <p className="mt-1">{s.summary}</p>
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-accent">{a.showRationale}</summary>
                <div className="mt-2">
                  <RationaleList items={s.rationale} risks={s.risks} />
                </div>
              </details>
            </article>
          ))}
        </div>
      </Card>
      <Card title={a.runsTitle}>
        {runs.isLoading && <p>{pl.common.loading}</p>}
        {runs.isError && <ErrorMessage message={pl.common.genericError} />}
        {runs.data?.length === 0 && <p className="text-muted">{a.runsEmpty}</p>}
        {runs.data && runs.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr>
                  <th className="py-1 pr-3">{a.colDate}</th>
                  <th className="py-1 pr-3">{a.colTask}</th>
                  <th className="py-1 pr-3">{a.colStatus}</th>
                  <th className="py-1 pr-3">{a.colAttempts}</th>
                  <th className="py-1">{a.colDuration}</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="py-1.5 pr-3">
                      <Link className="text-accent hover:underline" to={`/assistant/runs/${r.id}`}>
                        {formatDateTime(r.created_at)}
                      </Link>
                    </td>
                    <td className="py-1.5 pr-3">{a.kind[r.task] ?? r.task}</td>
                    <td className="py-1.5 pr-3">
                      <Badge tone={runTone(r.status)}>{a.runStatus[r.status] ?? r.status}</Badge>
                    </td>
                    <td className="py-1.5 pr-3">{r.attempts}</td>
                    <td className="py-1.5">{formatSeconds(r.duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
