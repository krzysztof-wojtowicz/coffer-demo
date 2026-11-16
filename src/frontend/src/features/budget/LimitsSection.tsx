import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { useCategories } from '../transactions/queries'
import { useDeleteLimit, useLimits, useSetLimit } from './queries'

const t = pl.summary
const AMOUNT_RE = /^\d+([.,]\d{1,2})?$/

export function LimitsSection() {
  const limits = useLimits()
  const categories = useCategories()
  const setLimit = useSetLimit()
  const del = useDeleteLimit()
  const [categoryId, setCategoryId] = useState('')
  const [amount, setAmount] = useState('')
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [pending, setPending] = useState<{ id: number; name: string } | null>(null)

  const options = (categories.data ?? []).filter((c) => c.in_budget)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const v = amount.trim()
    if (!categoryId) return setFieldError(t.limitChooseCategory)
    if (!AMOUNT_RE.test(v) || Number(v.replace(',', '.')) <= 0) return setFieldError(t.limitInvalidAmount)
    setFieldError(null)
    setLimit.mutate(
      { categoryId: Number(categoryId), amount: v.replace(',', '.') },
      { onSuccess: () => setAmount('') },
    )
  }
  const edit = (id: number, value: string) => {
    setCategoryId(String(id))
    setAmount(value.replace('.', ','))
    setFieldError(null)
  }
  const error = setLimit.error ?? del.error

  return (
    <Card title={t.limitsManage}>
      <ConfirmDialog
        open={pending !== null}
        title={t.limitDeleteTitle}
        message={pending ? t.limitDeleteMessage(pending.name) : undefined}
        confirmLabel={t.limitDelete}
        pending={del.isPending}
        onConfirm={() => {
          if (pending) del.mutate(pending.id, { onSettled: () => setPending(null) })
        }}
        onCancel={() => setPending(null)}
      />
      <form onSubmit={submit} noValidate className="mb-4 flex flex-wrap items-end gap-3">
        <Field label={t.limitCategory}>
          <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">{t.limitChooseCategory}</option>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t.limitAmount}>
          <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        <Button type="submit" loading={setLimit.isPending}>
          {t.limitSave}
        </Button>
      </form>
      {fieldError && (
        <p role="alert" className="mb-3 text-sm text-negative">
          {fieldError}
        </p>
      )}
      {error && <ErrorMessage message={apiErrorMessage(error) || t.limitSaveError} />}
      {limits.data?.length === 0 && <p className="text-muted">{t.limitsEmpty}</p>}
      {limits.data && limits.data.length > 0 && (
        <ul className="divide-y divide-border">
          {limits.data.map((l) => (
            <li key={l.category_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span>{l.category_name}</span>
              <span className="flex items-center gap-2">
                <span className="tabular-nums">
                  <Money value={l.amount} />
                </span>
                <Button variant="ghost" size="sm" onClick={() => edit(l.category_id, l.amount)}>
                  {pl.portfolio.editAction}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPending({ id: l.category_id, name: l.category_name })}
                >
                  {t.limitDelete}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
