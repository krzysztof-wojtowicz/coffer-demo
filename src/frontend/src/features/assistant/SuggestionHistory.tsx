import { useEffect, useState } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DatePicker } from '../../components/ui/DatePicker'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import { ActionReport } from './ActionReport'
import { actionDisplay, formatDateTime } from './labels'
import { SourceBadge } from './parts'
import { useActions, useSuggestions, type SuggestionFilters } from './queries'

const A = pl.assistant

const EMPTY: SuggestionFilters = { action: '', source: '', date_from: '', date_to: '', q: '', order: 'desc' }

export function SuggestionHistory() {
  const [filters, setFilters] = useState<SuggestionFilters>(EMPTY)
  const [search, setSearch] = useState('')
  const actions = useActions()
  const query = useSuggestions(filters)

  // Debounce the free-text search so every keystroke does not hit the API.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => (f.q === search ? f : { ...f, q: search })), 300)
    return () => clearTimeout(t)
  }, [search])

  const set = (patch: Partial<SuggestionFilters>) => setFilters((f) => ({ ...f, ...patch }))
  const items = query.data?.pages.flatMap((p) => p.items) ?? []
  const total = query.data?.pages[0]?.total ?? 0
  const filtered = Object.entries(filters).some(([k, v]) => k !== 'order' && v !== '')
  const actionIds = [
    ...(actions.data?.map((a) => a.id) ?? []),
    ...['surplus', 'advisor'],
  ]

  return (
    <Card title={A.historyTitle}>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={A.filterAction}>
          <Select value={filters.action} onChange={(e) => set({ action: e.target.value })}>
            <option value="">{A.filterAll}</option>
            {actionIds.map((id) => (
              <option key={id} value={id}>
                {actionDisplay(id)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={A.filterSource}>
          <Select value={filters.source} onChange={(e) => set({ source: e.target.value })}>
            <option value="">{A.filterAll}</option>
            <option value="ai">{A.sourceAi}</option>
            <option value="rules">{A.sourceRules}</option>
          </Select>
        </Field>
        <Field label={A.sortLabel}>
          <Select
            value={filters.order}
            onChange={(e) => set({ order: e.target.value as 'asc' | 'desc' })}
          >
            <option value="desc">{A.sortNewest}</option>
            <option value="asc">{A.sortOldest}</option>
          </Select>
        </Field>
        <div className="flex flex-col gap-1 text-sm font-medium text-text">
          <span>{A.filterFrom}</span>
          <DatePicker
            aria-label={A.filterFrom}
            value={filters.date_from}
            max={filters.date_to || undefined}
            onChange={(v) => set({ date_from: v })}
          />
        </div>
        <div className="flex flex-col gap-1 text-sm font-medium text-text">
          <span>{A.filterTo}</span>
          <DatePicker
            aria-label={A.filterTo}
            value={filters.date_to}
            min={filters.date_from || undefined}
            onChange={(v) => set({ date_to: v })}
          />
        </div>
        <Field label={A.filterSearch}>
          <Input
            type="search"
            maxLength={100}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Field>
      </div>
      {filtered && (
        <Button
          variant="ghost"
          size="sm"
          className="mb-3"
          onClick={() => {
            setSearch('')
            setFilters(EMPTY)
          }}
        >
          {A.filterReset}
        </Button>
      )}
      {query.isLoading && <p>{pl.common.loading}</p>}
      {query.isError && <ErrorMessage message={pl.common.genericError} />}
      {query.data && items.length === 0 && (
        <p className="text-muted">{filtered ? A.historyNoMatch : A.historyEmpty}</p>
      )}
      <ul className="space-y-2">
        {items.map((s) => (
          <li key={s.id}>
            <details className="rounded-md border border-border bg-surface-2 p-3">
              <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-sm font-semibold text-text">{actionDisplay(s.action)}</span>
                <span className="text-xs text-muted">{formatDateTime(s.created_at)}</span>
                <SourceBadge source={s.source} />
                <span className="basis-full text-sm text-text">{s.headline}</span>
              </summary>
              <div className="mt-3 border-t border-border pt-3">
                <ActionReport
                  report={s.report}
                  source={s.source}
                  aiStatus={s.ai_status}
                  runId={s.run_id}
                  showHeadline={false}
                  action={s.action}
                />
              </div>
            </details>
          </li>
        ))}
      </ul>
      {items.length > 0 && (
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-xs text-muted">{A.count(items.length, total)}</span>
          {query.hasNextPage && (
            <Button variant="secondary" loading={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
              {A.showMore}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
