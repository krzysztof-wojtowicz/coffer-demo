import { useMemo, useState, type ReactNode } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { MonthPicker } from '../../components/MonthPicker'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { currentMonth } from '../../lib/month'
import { ImportFlow } from '../import/ImportFlow'
import {
  defaultOptions,
  filterAndSort,
  uniqueSources,
  type ListOptions,
  type SortDir,
  type SortKey,
  type TypeFilter,
} from './list'
import { TransactionForm } from './TransactionForm'
import { TransactionRow } from './TransactionRow'
import { useCategories, useTransactions } from './queries'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-[8rem] flex-1 flex-col gap-1 lg:min-w-0">
      <span className="text-xs text-muted">{label}</span>
      {children}
    </div>
  )
}

type Panel = 'add' | 'import' | null

export function TransactionsPage() {
  const [month, setMonth] = useState(currentMonth())
  const [editingId, setEditingId] = useState<number | null>(null)
  const [panel, setPanel] = useState<Panel>(null)
  const [opts, setOpts] = useState<ListOptions>(defaultOptions)
  const categories = useCategories()
  const list = useTransactions(month)

  const toggle = (p: Exclude<Panel, null>) => setPanel((cur) => (cur === p ? null : p))
  const visible = useMemo(() => filterAndSort(list.data ?? [], opts), [list.data, opts])
  const sources = useMemo(() => uniqueSources(list.data ?? []), [list.data])
  const set = (patch: Partial<ListOptions>) => setOpts((o) => ({ ...o, ...patch }))

  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{pl.transactions.title}</h1>
      <div className="flex flex-wrap gap-2">
        <Button variant={panel === 'add' ? 'primary' : 'secondary'} onClick={() => toggle('add')}>
          {pl.transactions.add}
        </Button>
        <Button
          variant={panel === 'import' ? 'primary' : 'secondary'}
          onClick={() => toggle('import')}
        >
          {pl.transactions.importCsv}
        </Button>
      </div>
      {panel === 'add' && (
        <Card title={pl.transactions.add}>
          <TransactionForm />
        </Card>
      )}
      {panel === 'import' && <ImportFlow onFinished={() => setPanel(null)} />}

      <Card
        title={pl.transactions.title}
        actions={<MonthPicker value={month} onChange={setMonth} max={currentMonth()} />}
      >
        <div className="mb-3 flex flex-wrap items-end gap-2 lg:flex-nowrap">
          <Field label={pl.transactions.filterType}>
            <Select
              aria-label={pl.transactions.filterType}
              className="w-full"
              value={opts.type}
              onChange={(e) => set({ type: e.target.value as TypeFilter })}
            >
              <option value="all">{pl.transactions.typeAll}</option>
              <option value="income">{pl.transactions.typeIncome}</option>
              <option value="expense">{pl.transactions.typeExpense}</option>
            </Select>
          </Field>
          <Field label={pl.transactions.filterCategory}>
            <Select
              aria-label={pl.transactions.filterCategory}
              className="w-full"
              value={opts.categoryId ?? ''}
              onChange={(e) => set({ categoryId: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{pl.transactions.filterCategory}: {pl.transactions.all.toLowerCase()}</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={pl.transactions.filterSource}>
            <Select
              aria-label={pl.transactions.filterSource}
              className="w-full"
              value={opts.source ?? ''}
              onChange={(e) => set({ source: e.target.value || null })}
            >
              <option value="">{pl.transactions.filterSource}: {pl.transactions.all.toLowerCase()}</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s === 'import' ? pl.transactions.sourceImport : s === 'manual' ? pl.transactions.sourceManual : s}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={pl.transactions.sortBy}>
            <Select
              aria-label={pl.transactions.sortBy}
              className="w-full"
              value={opts.sortKey}
              onChange={(e) => set({ sortKey: e.target.value as SortKey })}
            >
              <option value="date">{pl.transactions.sortDate}</option>
              <option value="amount">{pl.transactions.sortAmount}</option>
            </Select>
          </Field>
          <Field label={pl.transactions.sortDir}>
            <Select
              aria-label={pl.transactions.sortDir}
              className="w-full"
              value={opts.sortDir}
              onChange={(e) => set({ sortDir: e.target.value as SortDir })}
            >
              <option value="desc">{pl.transactions.sortDesc}</option>
              <option value="asc">{pl.transactions.sortAsc}</option>
            </Select>
          </Field>
        </div>
        {list.isLoading && <Spinner />}
        {list.error && <ErrorMessage message={apiErrorMessage(list.error)} />}
        {list.data && list.data.length === 0 && (
          <p className="text-muted">{pl.transactions.empty}</p>
        )}
        {list.data && list.data.length > 0 && visible.length === 0 && (
          <p className="text-muted">{pl.transactions.emptyFiltered}</p>
        )}
        {visible.length > 0 && (
          <ul>
            {visible.map((t) => (
              <TransactionRow
                key={t.id}
                tx={t}
                categories={categories.data ?? []}
                editing={editingId === t.id}
                onEdit={() => setEditingId(t.id)}
                onClose={() => setEditingId(null)}
              />
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
