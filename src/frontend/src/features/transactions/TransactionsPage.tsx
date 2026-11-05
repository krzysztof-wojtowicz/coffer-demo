import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { MonthPicker } from '../../components/MonthPicker'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { currentMonth } from '../../lib/month'
import {
  useCategories,
  useCreateTransaction,
  useDeleteTransaction,
  useTransactions,
} from './queries'

const today = () => new Date().toISOString().slice(0, 10)

export function TransactionsPage() {
  const [month, setMonth] = useState(currentMonth())
  const [date, setDate] = useState(today())
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState<string>('')
  const categories = useCategories()
  const list = useTransactions(month)
  const create = useCreateTransaction()
  const del = useDeleteTransaction()

  const defaultId = categories.data?.find((c) => c.is_default)?.id
  const selected = categoryId || (defaultId !== undefined ? String(defaultId) : '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      {
        date,
        amount: amount.trim().replace(',', '.'),
        description,
        category_id: selected ? Number(selected) : null,
      },
      {
        onSuccess: () => {
          setAmount('')
          setDescription('')
        },
      },
    )
  }

  const remove = (id: number) => {
    if (window.confirm(pl.transactions.confirmDelete)) del.mutate(id)
  }

  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{pl.transactions.title}</h1>
      <Card title={pl.transactions.add}>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
          <Field label={pl.transactions.date}>
            <Input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field label={pl.transactions.amount}>
            <Input
              type="text"
              inputMode="decimal"
              required
              title={pl.transactions.amountHint}
              placeholder="-12,50"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </Field>
          <Field label={pl.transactions.description}>
            <Input
              type="text"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
          <Field label={pl.transactions.category}>
            <Select value={selected} onChange={(e) => setCategoryId(e.target.value)}>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Button type="submit" loading={create.isPending}>
            {pl.transactions.save}
          </Button>
        </form>
        <ErrorMessage message={create.error ? apiErrorMessage(create.error) : null} />
      </Card>

      <Card
        title={pl.transactions.title}
        actions={<MonthPicker value={month} onChange={setMonth} max={currentMonth()} />}
      >
        <ErrorMessage message={del.error ? apiErrorMessage(del.error) : null} />
        {list.isLoading && <Spinner />}
        {list.error && <ErrorMessage message={apiErrorMessage(list.error)} />}
        {list.data && list.data.length === 0 && (
          <p className="text-muted">{pl.transactions.empty}</p>
        )}
        {list.data && list.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 pr-3 font-medium">{pl.transactions.date}</th>
                  <th className="py-2 pr-3 font-medium">{pl.transactions.description}</th>
                  <th className="py-2 pr-3 font-medium">{pl.transactions.category}</th>
                  <th className="py-2 pr-3 font-medium">{pl.transactions.source}</th>
                  <th className="py-2 pr-3 text-right font-medium">{pl.transactions.amount}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.data.map((t) => (
                  <tr key={t.id} className="border-b border-border/60">
                    <td className="py-2 pr-3 whitespace-nowrap">{t.date}</td>
                    <td className="py-2 pr-3">{t.description}</td>
                    <td className="py-2 pr-3">{t.category_name}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={t.source === 'import' ? 'info' : 'neutral'}>
                        {t.source === 'import'
                          ? pl.transactions.sourceImport
                          : pl.transactions.sourceManual}
                      </Badge>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <Money value={t.amount} colored />
                    </td>
                    <td className="py-2 text-right">
                      <Button variant="ghost" size="sm" onClick={() => remove(t.id)}>
                        {pl.transactions.delete}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
