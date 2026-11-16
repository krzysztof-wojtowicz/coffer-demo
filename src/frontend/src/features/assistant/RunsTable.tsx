import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DatePicker } from '../../components/ui/DatePicker'
import { Field } from '../../components/ui/Field'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import {
  actionDisplay,
  formatCost,
  formatDateTime,
  formatMs,
  formatTokens,
  providerLabel,
  runStatusLabel,
  runTone,
} from './labels'
import { RUNS_PAGE, useActions, useRuns, type RunFilters, type RunSort } from './queries'

const A = pl.assistant

const EMPTY: RunFilters = {
  action: '',
  status: '',
  provider: '',
  date_from: '',
  date_to: '',
  sort: 'created_at',
  order: 'desc',
  page: 1,
}

const STATUSES = ['ok', 'invalid', 'unavailable', 'limited', 'timeout', 'no_data', 'error']
const PROVIDERS = ['ollama', 'anthropic', 'gemini', 'openai']

export function RunsTable() {
  const [f, setF] = useState<RunFilters>(EMPTY)
  const actions = useActions()
  const query = useRuns(f)
  const set = (patch: Partial<RunFilters>) => setF((p) => ({ ...p, page: 1, ...patch }))
  const sortBy = (sort: RunSort) =>
    setF((p) => ({
      ...p,
      page: 1,
      sort,
      order: p.sort === sort && p.order === 'desc' ? 'asc' : 'desc',
    }))
  const ariaSort = (s: RunSort) =>
    f.sort === s ? (f.order === 'asc' ? 'ascending' : 'descending') : 'none'
  const sortTh = (s: RunSort, label: string) => (
    <th scope="col" aria-sort={ariaSort(s)} className="py-1 pr-3 font-medium">
      <button type="button" className="cursor-pointer hover:text-text" onClick={() => sortBy(s)}>
        {label}
        {f.sort === s ? (f.order === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  )

  const items = query.data?.items ?? []
  const total = query.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / RUNS_PAGE))
  const actionIds = [...(actions.data?.map((a) => a.id) ?? []), 'surplus', 'advisor']
  const filtered = f.action || f.status || f.provider || f.date_from || f.date_to

  return (
    <Card title={A.runsTitle}>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Field label={A.filterAction}>
          <Select value={f.action} onChange={(e) => set({ action: e.target.value })}>
            <option value="">{A.filterAll}</option>
            {actionIds.map((id) => (
              <option key={id} value={id}>
                {actionDisplay(id)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={A.filterStatus}>
          <Select value={f.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="">{A.filterAll}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {runStatusLabel(s)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={A.filterProvider}>
          <Select value={f.provider} onChange={(e) => set({ provider: e.target.value })}>
            <option value="">{A.filterAll}</option>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {providerLabel(p)}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex flex-col gap-1 text-sm font-medium text-text">
          <span>{A.filterFrom}</span>
          <DatePicker
            aria-label={`${A.runsTitle}: ${A.filterFrom}`}
            value={f.date_from}
            max={f.date_to || undefined}
            onChange={(v) => set({ date_from: v })}
          />
        </div>
        <div className="flex flex-col gap-1 text-sm font-medium text-text">
          <span>{A.filterTo}</span>
          <DatePicker
            aria-label={`${A.runsTitle}: ${A.filterTo}`}
            value={f.date_to}
            min={f.date_from || undefined}
            onChange={(v) => set({ date_to: v })}
          />
        </div>
      </div>
      {filtered && (
        <Button
          variant="ghost"
          size="sm"
          className="mb-3"
          onClick={() => setF({ ...EMPTY, sort: f.sort, order: f.order })}
        >
          {A.filterReset}
        </Button>
      )}
      {query.isLoading && <p>{pl.common.loading}</p>}
      {query.isError && <ErrorMessage message={pl.common.genericError} />}
      {query.data && items.length === 0 && <p className="text-muted">{A.runsEmpty}</p>}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{A.runsTitle}</caption>
            <thead className="text-muted">
              <tr>
                {sortTh('created_at', A.colDate)}
                <th scope="col" className="py-1 pr-3 font-medium">{A.colAction}</th>
                <th scope="col" className="py-1 pr-3 font-medium">{A.colStatus}</th>
                <th scope="col" className="py-1 pr-3 font-medium">{A.colProvider}</th>
                <th scope="col" className="py-1 pr-3 font-medium">{A.colModel}</th>
                {sortTh('tokens', A.colTokens)}
                {sortTh('cost_usd', A.colCost)}
                {sortTh('duration_ms', A.colDuration)}
                <th scope="col" className="py-1 font-medium">{A.colTools}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className="border-t border-border">
                  <th scope="row" className="whitespace-nowrap py-1.5 pr-3 text-left font-normal">
                    <Link className="text-accent hover:underline" to={`/assistant/runs/${r.id}`}>
                      {formatDateTime(r.created_at)}
                    </Link>
                  </th>
                  <td className="py-1.5 pr-3">{actionDisplay(r.action)}</td>
                  <td className="py-1.5 pr-3">
                    <Badge tone={runTone(r.status)}>{runStatusLabel(r.status)}</Badge>
                  </td>
                  <td className="py-1.5 pr-3">{providerLabel(r.provider)}</td>
                  <td className="py-1.5 pr-3">{r.model ?? '—'}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{formatTokens(r.input_tokens, r.output_tokens)}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{formatCost(r.cost_usd)}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{formatMs(r.duration_ms)}</td>
                  <td className="py-1.5 tabular-nums">{r.tool_calls_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > RUNS_PAGE && (
        <div className="mt-3 flex items-center justify-between gap-3">
          <Button variant="secondary" size="sm" disabled={f.page <= 1} onClick={() => setF((p) => ({ ...p, page: p.page - 1 }))}>
            {A.prevPage}
          </Button>
          <span className="text-xs text-muted">{A.page(f.page, pages)}</span>
          <Button variant="secondary" size="sm" disabled={f.page >= pages} onClick={() => setF((p) => ({ ...p, page: p.page + 1 }))}>
            {A.nextPage}
          </Button>
        </div>
      )}
    </Card>
  )
}
