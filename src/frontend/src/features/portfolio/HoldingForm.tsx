import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DatePicker } from '../../components/ui/DatePicker'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import { CLASS_CONFIG, FIELD_KEYS, type FieldKey, type FieldSpec } from './fields'
import {
  ASSET_CLASSES,
  useCreateHolding,
  useUpdateHolding,
  type AssetClass,
  type Holding,
} from './queries'

const t = pl.portfolio

type FormState = {
  name: string
  asset_class: AssetClass | ''
  note: string
} & Record<FieldKey, string>

const EMPTY: FormState = {
  name: '',
  asset_class: '',
  symbol: '',
  currency: 'PLN',
  quantity: '',
  purchase_price: '',
  purchase_date: '',
  manual_value: '',
  note: '',
}

const num = (s: string) => s.trim().replace(/\s/g, '').replace(',', '.')
const orNull = (s: string) => (s.trim() ? s.trim() : null)

function fromHolding(h: Holding): FormState {
  return {
    name: h.name,
    asset_class: h.asset_class,
    symbol: h.symbol ?? '',
    currency: h.currency,
    quantity: h.quantity,
    purchase_price: h.purchase_price,
    purchase_date: h.purchase_date ?? '',
    manual_value: h.manual_value ?? '',
    note: h.note ?? '',
  }
}

/** Body for the API: only fields visible for the class; hidden ones get backend defaults or null. */
export function toBody(f: FormState & { asset_class: AssetClass }, editing?: Holding | null) {
  const cfg = CLASS_CONFIG[f.asset_class]
  const shown = new Set(cfg.fields.map((s) => s.key))
  const has = (k: FieldKey) => shown.has(k)
  return {
    name: f.name.trim(),
    asset_class: f.asset_class,
    symbol: has('symbol') ? (orNull(f.symbol)?.toUpperCase() ?? null) : null,
    quantity: has('quantity')
      ? num(f.quantity)
      : editing
        ? editing.quantity
        : (cfg.fixed?.quantity ?? '1'),
    purchase_price: num(f.purchase_price),
    currency: (has('currency') ? f.currency.trim().toUpperCase() : '') || 'PLN',
    purchase_date: has('purchase_date') ? orNull(f.purchase_date) : null,
    manual_value: has('manual_value') ? orNull(num(f.manual_value)) : null,
    note: orNull(f.note),
  }
}

/** Polski komunikat z błędu API portfela (detail string albo lista błędów walidacji). */
export function portfolioErrorMessage(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string; type?: string }) => {
        const field = String(d.loc?.[d.loc.length - 1] ?? '')
        const name = t.fieldNames[field]
        if (d.type === 'value_error' && d.msg) return d.msg.replace(/^Value error, /, '')
        if (d.type?.includes('missing')) return `${name ?? field}: ${pl.validation.required}`
        return `${name ?? field}: ${pl.validation.invalid}`
      })
      .join('; ')
  }
  return pl.common.genericError
}

function Hint({ children }: { children: string }) {
  return <span className="text-xs font-normal text-muted">{children}</span>
}

export function HoldingForm({ editing, onDone }: { editing: Holding | null; onDone: () => void }) {
  const [form, setForm] = useState<FormState>(editing ? fromHolding(editing) : EMPTY)
  const create = useCreateHolding()
  const update = useUpdateHolding()
  const mutation = editing ? update : create
  const set = (k: keyof FormState) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  const cls = form.asset_class
  const cfg = cls ? CLASS_CONFIG[cls] : null

  /** Changing the class clears fields the new class does not have. */
  const changeClass = (value: string) =>
    setForm((f) => {
      const next = value as AssetClass
      const keep = new Set(CLASS_CONFIG[next].fields.map((s) => s.key))
      const cleared = { ...f, asset_class: next }
      for (const k of FIELD_KEYS) if (!keep.has(k)) cleared[k] = EMPTY[k]
      return cleared
    })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!cls) return
    const body = toBody({ ...form, asset_class: cls }, editing)
    if (editing) {
      update.mutate({ id: editing.id, body }, { onSuccess: onDone })
    } else {
      create.mutate(body, { onSuccess: () => setForm(EMPTY) })
    }
  }

  const renderField = (spec: FieldSpec) => {
    const text = t.fieldText[spec.text ?? spec.key]
    const label = spec.required ? text.label : `${text.label} ${t.optional}`
    const common = { value: form[spec.key], onChange: set(spec.key) }
    let control
    if (spec.key === 'purchase_date') {
      control = (
        <DatePicker value={form.purchase_date} onChange={(v) => setForm((f) => ({ ...f, purchase_date: v }))} />
      )
    } else if (spec.key === 'currency') {
      control = <Input required maxLength={3} {...common} />
    } else if (spec.key === 'symbol') {
      control = <Input required={spec.required} maxLength={20} placeholder={spec.placeholder} {...common} />
    } else {
      control = (
        <Input required={spec.required} inputMode="decimal" placeholder={spec.placeholder} {...common} />
      )
    }
    return (
      <Field key={spec.key} label={label}>
        {control}
        <Hint>{text.hint}</Hint>
      </Field>
    )
  }

  return (
    <Card title={editing ? t.edit : t.add}>
      <div className="mb-3 space-y-1 rounded-md bg-surface-2 px-3 py-2 text-xs text-muted" aria-label={t.autoLegendTitle}>
        <p className="font-medium text-text">{t.autoLegendTitle}</p>
        <p>{t.autoLegendAuto}</p>
        <p>{t.autoLegendManual}</p>
      </div>
      <form
        onSubmit={submit}
        className="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-4"
        aria-label={editing ? t.edit : t.add}
      >
        <Field label={t.assetClass}>
          <Select required value={form.asset_class} onChange={(e) => changeClass(e.target.value)}>
            <option value="" disabled>
              {t.chooseClass}
            </option>
            {ASSET_CLASSES.map((c) => (
              <option key={c} value={c}>
                {t.classes[c]}
              </option>
            ))}
          </Select>
          <Hint>{cfg ? (cfg.auto ? t.autoClassNote : t.manualClassNote) : t.chooseClassHint}</Hint>
        </Field>
        <Field label={t.name}>
          <Input required maxLength={100} value={form.name} onChange={set('name')} />
          <Hint>{t.nameHint}</Hint>
        </Field>
        {cfg?.fields.map(renderField)}
        {cfg && (
          <Field label={`${t.note} ${t.optional}`} className="sm:col-span-2 lg:col-span-3">
            <Input maxLength={500} value={form.note} onChange={set('note')} />
            <Hint>{t.noteHint}</Hint>
          </Field>
        )}
        {cfg && (
          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-1">
            <Button type="submit" loading={mutation.isPending}>
              {editing ? t.update : t.save}
            </Button>
            {editing && (
              <Button type="button" variant="secondary" onClick={onDone}>
                {t.cancel}
              </Button>
            )}
          </div>
        )}
      </form>
      <ErrorMessage message={mutation.error ? portfolioErrorMessage(mutation.error) : null} />
    </Card>
  )
}
