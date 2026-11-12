import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { DatePicker } from '../../components/ui/DatePicker'
import { Select } from '../../components/ui/Select'
import { todayIso } from '../../lib/date'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { useCategories, useCreateTransaction } from './queries'


export function TransactionForm() {
  const [date, setDate] = useState(todayIso())
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState<string>('')
  const categories = useCategories()
  const create = useCreateTransaction()

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

  return (
    <>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
        <Field label={pl.transactions.date}>
          <DatePicker required value={date} onChange={setDate} />
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
    </>
  )
}
