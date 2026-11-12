import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { DatePicker } from '../../components/ui/DatePicker'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { categoryTagClass } from './list'
import {
  useDeleteTransaction,
  useUpdateTransaction,
  type TransactionOut,
} from './queries'

type Category = { id: number; name: string }

export function TransactionRow({
  tx,
  categories,
  editing,
  onEdit,
  onClose,
}: {
  tx: TransactionOut
  categories: Category[]
  editing: boolean
  onEdit: () => void
  onClose: () => void
}) {
  return (
    <li className="border-b border-border/60 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="w-20 shrink-0 text-xs text-muted whitespace-nowrap">{tx.date}</span>
        <span className="w-28 shrink-0 text-right text-sm">
          <Money value={tx.amount} colored />
        </span>
        <span className="min-w-0 flex-1 truncate text-sm">{tx.description}</span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${categoryTagClass(tx.category_id)}`}
        >
          {tx.category_name}
        </span>
        <span className="w-16 shrink-0 text-xs text-muted">
          {tx.source === 'import'
            ? pl.transactions.sourceImport
            : tx.source === 'manual'
              ? pl.transactions.sourceManual
              : tx.source}
        </span>
        <Button variant="ghost" size="sm" onClick={editing ? onClose : onEdit}>
          {pl.transactions.edit}
        </Button>
      </div>
      {editing && (
        <EditForm tx={tx} categories={categories} onClose={onClose} />
      )}
    </li>
  )
}

function EditForm({
  tx,
  categories,
  onClose,
}: {
  tx: TransactionOut
  categories: Category[]
  onClose: () => void
}) {
  const [date, setDate] = useState(tx.date)
  const [amount, setAmount] = useState(tx.amount)
  const [description, setDescription] = useState(tx.description)
  const [categoryId, setCategoryId] = useState(String(tx.category_id))
  const update = useUpdateTransaction()
  const del = useDeleteTransaction()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    update.mutate(
      {
        id: tx.id,
        body: {
          date,
          amount: amount.trim().replace(',', '.'),
          description,
          category_id: Number(categoryId),
        },
      },
      { onSuccess: onClose },
    )
  }
  const [confirming, setConfirming] = useState(false)
  const remove = () => del.mutate(tx.id, { onSuccess: onClose })
  const error = update.error ?? del.error

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-lg bg-surface-2 p-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label={pl.transactions.date}>
          <DatePicker required value={date} onChange={setDate} />
        </Field>
        <Field label={pl.transactions.amount}>
          <Input
            type="text"
            inputMode="decimal"
            required
            title={pl.transactions.amountHint}
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
          <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <ErrorMessage message={error ? apiErrorMessage(error) : null} />
      <div className="flex gap-2">
        <Button type="submit" loading={update.isPending}>
          {pl.transactions.confirm}
        </Button>
        <Button type="button" variant="secondary" onClick={onClose}>
          {pl.transactions.cancel}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setConfirming(true)} loading={del.isPending}>
          {pl.transactions.delete}
        </Button>
      </div>
      <ConfirmDialog
        open={confirming}
        title={pl.transactions.confirmDelete}
        pending={del.isPending}
        onConfirm={remove}
        onCancel={() => setConfirming(false)}
      />
    </form>
  )
}
