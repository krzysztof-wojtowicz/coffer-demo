import { useEffect, useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { DatePicker } from '../../components/ui/DatePicker'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { todayIso } from '../../lib/date'
import { pl } from '../../i18n/pl'
import { useDeleteOpeningBalance, useOpeningBalance, useSaveOpeningBalance } from './queries'


export function OpeningBalanceSection() {
  const t = pl.openingBalance
  const query = useOpeningBalance()
  const save = useSaveOpeningBalance()
  const del = useDeleteOpeningBalance()
  const [amount, setAmount] = useState('')
  const [asOf, setAsOf] = useState(todayIso())
  const [localError, setLocalError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    if (query.data) {
      setAmount(query.data.amount.replace('.', ','))
      setAsOf(query.data.as_of)
    }
  }, [query.data])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSaved(false)
    const normalized = amount.trim().replace(/\s/g, '').replace(',', '.')
    if (!/^-?\d+(\.\d{1,2})?$/.test(normalized)) {
      setLocalError(t.invalidAmount)
      return
    }
    if (asOf > todayIso()) {
      setLocalError(t.futureDate)
      return
    }
    setLocalError(null)
    save.mutate({ amount: normalized, as_of: asOf }, { onSuccess: () => setSaved(true) })
  }

  const remove = () =>
    del.mutate(undefined, {
      onSuccess: () => {
        setConfirming(false)
        setAmount('')
        setAsOf(todayIso())
        setSaved(false)
      },
      onError: () => setConfirming(false),
    })

  const mutationError = save.error?.message ?? del.error?.message ?? null

  return (
    <Card title={t.title}>
      <p className="mb-3 text-sm text-muted">{t.hint}</p>
      {query.isPending ? (
        <Spinner className="size-5" />
      ) : (
        <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
          <Field label={t.amount}>
            <Input
              type="text"
              inputMode="decimal"
              required
              placeholder="1234,56"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </Field>
          <Field label={t.asOf}>
            <DatePicker value={asOf} onChange={setAsOf} max={todayIso()} required aria-label={t.asOf} />
          </Field>
          <ErrorMessage message={localError ?? mutationError} />
          {saved && (
            <p className="text-sm text-positive" role="status">
              {t.saved}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="submit" loading={save.isPending}>
              {t.save}
            </Button>
            {query.data && (
              <Button type="button" variant="secondary" onClick={() => setConfirming(true)}>
                {t.remove}
              </Button>
            )}
          </div>
        </form>
      )}
      <ConfirmDialog
        open={confirming}
        title={t.confirmTitle}
        message={t.confirmMessage}
        pending={del.isPending}
        onConfirm={remove}
        onCancel={() => setConfirming(false)}
      />
    </Card>
  )
}
