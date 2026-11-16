import type { FormEvent } from 'react'
import { MonthPicker } from '../../components/MonthPicker'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { pl } from '../../i18n/pl'
import { currentMonth } from '../../lib/month'
import { optionLabel } from './labels'
import type { ParamSpec } from './queries'

const A = pl.assistant

export type FormValues = Record<string, string>
export type FormErrors = Record<string, string>

/** Initial value of a field: URL/deep-link value, else the spec default, else the current month. */
export function initialValue(spec: ParamSpec, fromUrl: string | null | undefined): string {
  if (fromUrl != null && fromUrl !== '') return fromUrl
  if (spec.default != null) return String(spec.default)
  return ''
}

const MONEY_RE = /^\d+([.,]\d{1,2})?$/
const QTY_RE = /^\d+([.,]\d{1,8})?$/

/** Validates values by ParamSpec kinds; returns Polish messages keyed by param name. */
export function validateParams(specs: ParamSpec[], values: FormValues): FormErrors {
  const errors: FormErrors = {}
  for (const s of specs) {
    const v = (values[s.name] ?? '').trim()
    if (v === '') {
      if (s.required) errors[s.name] = A.required
      continue
    }
    if (s.kind === 'amount' || s.kind === 'quantity') {
      const re = s.kind === 'amount' ? MONEY_RE : QTY_RE
      if (!re.test(v)) errors[s.name] = s.kind === 'amount' ? A.invalidMoney : A.invalidAmount
      else if (Number(v.replace(',', '.')) <= 0) errors[s.name] = A.invalidAmount
    } else if (s.kind === 'int') {
      if (!/^\d+$/.test(v)) errors[s.name] = A.invalidInt
    }
  }
  return errors
}

/** Builds the `params` request body; empty optional fields are omitted. */
export function buildParams(specs: ParamSpec[], values: FormValues): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const s of specs) {
    const v = (values[s.name] ?? '').trim()
    if (v === '') continue
    if (s.kind === 'amount' || s.kind === 'quantity') out[s.name] = v.replace(',', '.')
    else if (s.kind === 'int') out[s.name] = Number(v)
    else out[s.name] = v
  }
  return out
}

/** Form generated from the action catalogue (ParamSpec), no per-action code. */
export function ActionForm({
  specs,
  values,
  errors,
  running,
  onChange,
  onSubmit,
  onCancel,
}: {
  specs: ParamSpec[]
  values: FormValues
  errors: FormErrors
  running: boolean
  onChange: (name: string, value: string) => void
  onSubmit: () => void
  onCancel: () => void
}) {
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!running) onSubmit()
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      {specs.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {specs.map((s) => {
            const v = values[s.name] ?? ''
            const label = s.required ? `${s.label} *` : s.label
            const help = s.help ? <span className="text-xs font-normal text-muted">{s.help}</span> : null
            if (s.kind === 'month') {
              return (
                <div key={s.name} className="flex flex-col gap-1 text-sm font-medium text-text">
                  <span>{label}</span>
                  {v ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <MonthPicker value={v} onChange={(m) => onChange(s.name, m)} max={currentMonth()} />
                      {!s.required && (
                        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(s.name, '')}>
                          {A.monthClear}
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-normal text-muted">{A.monthDefault(s.help ?? null)}</span>
                      <Button type="button" variant="secondary" size="sm" onClick={() => onChange(s.name, currentMonth())}>
                        {A.monthPick}
                      </Button>
                    </div>
                  )}
                  {errors[s.name] && (
                    <span role="alert" className="text-xs font-normal text-negative">
                      {errors[s.name]}
                    </span>
                  )}
                </div>
              )
            }
            if (s.kind === 'select') {
              return (
                <Field key={s.name} label={label} error={errors[s.name]}>
                  <Select value={v} onChange={(e) => onChange(s.name, e.target.value)}>
                    {s.required ? (
                      <option value="" disabled>
                        {A.selectPlaceholder}
                      </option>
                    ) : (
                      <option value="">{A.selectPlaceholder}</option>
                    )}
                    {s.options.map((o) => (
                      <option key={o} value={o}>
                        {optionLabel(s.name, o)}
                      </option>
                    ))}
                  </Select>
                  {help}
                </Field>
              )
            }
            const numeric = s.kind === 'amount' || s.kind === 'quantity' || s.kind === 'int'
            return (
              <Field key={s.name} label={label} error={errors[s.name]}>
                <Input
                  value={v}
                  inputMode={numeric ? 'decimal' : undefined}
                  autoComplete="off"
                  aria-invalid={errors[s.name] ? true : undefined}
                  onChange={(e) => onChange(s.name, e.target.value)}
                />
                {help}
              </Field>
            )
          })}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={running}>
          {running ? A.running : A.run}
        </Button>
        {running && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            {A.cancel}
          </Button>
        )}
      </div>
    </form>
  )
}
