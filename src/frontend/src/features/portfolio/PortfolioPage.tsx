import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { AdvisorPanel } from './AdvisorPanel'
import {
  ASSET_CLASSES,
  useCreateHolding,
  useDeleteHolding,
  useHoldings,
  usePortfolioSummary,
  useUpdateHolding,
  type AdviceHoldingIn,
  type AssetClass,
  type Holding,
  type PortfolioSummary,
} from './queries'

const t = pl.portfolio

type FormState = {
  name: string
  symbol: string
  asset_class: AssetClass
  quantity: string
  purchase_price: string
  currency: string
  purchase_date: string
  manual_value: string
  note: string
}

const EMPTY: FormState = {
  name: '',
  symbol: '',
  asset_class: 'stock',
  quantity: '',
  purchase_price: '',
  currency: 'PLN',
  purchase_date: '',
  manual_value: '',
  note: '',
}

const num = (s: string) => s.trim().replace(/\s/g, '').replace(',', '.')
const orNull = (s: string) => (s.trim() ? s.trim() : null)

function fromHolding(h: Holding): FormState {
  return {
    name: h.name,
    symbol: h.symbol ?? '',
    asset_class: h.asset_class,
    quantity: h.quantity,
    purchase_price: h.purchase_price,
    currency: h.currency,
    purchase_date: h.purchase_date ?? '',
    manual_value: h.manual_value ?? '',
    note: h.note ?? '',
  }
}

function toBody(f: FormState) {
  return {
    name: f.name,
    symbol: orNull(f.symbol),
    asset_class: f.asset_class,
    quantity: num(f.quantity),
    purchase_price: num(f.purchase_price),
    currency: f.currency.trim().toUpperCase() || 'PLN',
    purchase_date: orNull(f.purchase_date),
    manual_value: orNull(num(f.manual_value)),
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

function formatAmount(value: string, currency: string): string {
  try {
    return new Intl.NumberFormat('pl-PL', { style: 'currency', currency }).format(Number(value))
  } catch {
    return `${value} ${currency}`
  }
}

function Pct({ value }: { value: string | null }) {
  if (value === null) return <span className="text-muted">–</span>
  const neg = value.startsWith('-')
  const zero = Number(value) === 0
  return (
    <span className={cn('tabular-nums', neg && 'text-negative', !neg && !zero && 'text-positive')}>
      {neg || zero ? '' : '+'}
      {value.replace('.', ',')}%
    </span>
  )
}

function HoldingForm({ editing, onDone }: { editing: Holding | null; onDone: () => void }) {
  const [form, setForm] = useState<FormState>(editing ? fromHolding(editing) : EMPTY)
  const create = useCreateHolding()
  const update = useUpdateHolding()
  const mutation = editing ? update : create
  const set = (k: keyof FormState) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const body = toBody(form)
    if (editing) {
      update.mutate({ id: editing.id, body }, { onSuccess: onDone })
    } else {
      create.mutate(body, { onSuccess: () => setForm(EMPTY) })
    }
  }

  return (
    <Card title={editing ? t.edit : t.add}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label={editing ? t.edit : t.add}>
        <Field label={t.name}>
          <Input required maxLength={100} value={form.name} onChange={set('name')} />
        </Field>
        <Field label={t.assetClass}>
          <Select value={form.asset_class} onChange={set('asset_class')}>
            {ASSET_CLASSES.map((c) => (
              <option key={c} value={c}>
                {t.classes[c]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={`${t.symbol} ${t.optional}`}>
          <Input maxLength={20} title={t.symbolHint} placeholder="AAPL" value={form.symbol} onChange={set('symbol')} />
        </Field>
        <Field label={t.currency}>
          <Input required maxLength={3} value={form.currency} onChange={set('currency')} />
        </Field>
        <Field label={t.quantity}>
          <Input required inputMode="decimal" placeholder="10" value={form.quantity} onChange={set('quantity')} />
        </Field>
        <Field label={t.purchasePrice}>
          <Input
            required
            inputMode="decimal"
            placeholder="100,00"
            value={form.purchase_price}
            onChange={set('purchase_price')}
          />
        </Field>
        <Field label={`${t.purchaseDate} ${t.optional}`}>
          <Input type="date" value={form.purchase_date} onChange={set('purchase_date')} />
        </Field>
        <Field label={`${t.manualValue} ${t.optional}`}>
          <Input
            inputMode="decimal"
            title={t.manualValueHint}
            value={form.manual_value}
            onChange={set('manual_value')}
          />
        </Field>
        <Field label={`${t.note} ${t.optional}`} className="sm:col-span-2 lg:col-span-3">
          <Input maxLength={500} value={form.note} onChange={set('note')} />
        </Field>
        <div className="flex items-end gap-2">
          <Button type="submit" loading={mutation.isPending}>
            {editing ? t.update : t.save}
          </Button>
          {editing && (
            <Button type="button" variant="secondary" onClick={onDone}>
              {t.cancel}
            </Button>
          )}
        </div>
      </form>
      <p className="mt-2 text-xs text-muted">{t.manualValueHint}</p>
      <ErrorMessage message={mutation.error ? portfolioErrorMessage(mutation.error) : null} />
    </Card>
  )
}

function SummaryTiles({ s }: { s: PortfolioSummary }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card>
        <div className="text-sm text-muted">{t.totalValue}</div>
        <div className="mt-1 text-2xl font-semibold">
          <Money value={s.total_value} />
        </div>
      </Card>
      <Card>
        <div className="text-sm text-muted">{t.totalCost}</div>
        <div className="mt-1 text-2xl font-semibold">
          <Money value={s.total_cost} />
        </div>
      </Card>
      <Card>
        <div className="text-sm text-muted">{t.totalGain}</div>
        <div className="mt-1 text-2xl font-semibold">
          <Money value={s.total_gain} colored />
        </div>
        <div className="text-sm">
          <Pct value={s.total_gain_pct} />
        </div>
      </Card>
    </div>
  )
}

function Allocation({ s }: { s: PortfolioSummary }) {
  return (
    <Card title={t.allocation}>
      {s.allocation.length === 0 ? (
        <p className="text-muted">{t.noAllocation}</p>
      ) : (
        <ul className="space-y-3">
          {s.allocation.map((a) => (
            <li key={a.asset_class}>
              <div className="flex justify-between gap-2 text-sm">
                <span>{t.classes[a.asset_class]}</span>
                <span className="tabular-nums">
                  <Money value={a.value} /> · {a.share_pct.replace('.', ',')}%
                </span>
              </div>
              <div
                className="mt-1 h-2 rounded-full bg-surface-2"
                role="meter"
                aria-label={t.classes[a.asset_class]}
                aria-valuenow={Number(a.share_pct)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="h-2 rounded-full bg-accent" style={{ width: `${Math.min(100, Number(a.share_pct))}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function HoldingsTable({
  s,
  holdings,
  onEdit,
}: {
  s: PortfolioSummary
  holdings: Holding[]
  onEdit: (h: Holding) => void
}) {
  const del = useDeleteHolding()
  const byId = new Map(holdings.map((h) => [h.id, h]))
  const remove = (id: number) => {
    if (window.confirm(t.confirmDelete)) del.mutate(id)
  }
  return (
    <Card title={t.holdings}>
      <ErrorMessage message={del.error ? portfolioErrorMessage(del.error) : null} />
      {s.holdings.length === 0 ? (
        <p className="text-muted">{t.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="py-2 pr-3 font-medium">{t.name}</th>
                <th className="py-2 pr-3 font-medium">{t.assetClass}</th>
                <th className="py-2 pr-3 text-right font-medium">{t.quantity}</th>
                <th className="py-2 pr-3 text-right font-medium">{t.cost}</th>
                <th className="py-2 pr-3 text-right font-medium">{t.value}</th>
                <th className="py-2 pr-3 text-right font-medium">{t.gain}</th>
                <th className="py-2 pr-3 text-right font-medium">{t.share}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {s.holdings.map((v) => {
                const h = byId.get(v.id)
                return (
                  <tr key={v.id} className="border-b border-border/60">
                    <td className="py-2 pr-3">
                      <div>{v.name}</div>
                      {v.symbol && <div className="text-xs text-muted">{v.symbol}</div>}
                    </td>
                    <td className="py-2 pr-3">{t.classes[v.asset_class]}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{v.quantity.replace('.', ',')}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{formatAmount(v.cost_basis, v.amount_currency)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      <div>{formatAmount(v.current_value, v.amount_currency)}</div>
                      <Badge tone={v.value_source === 'market' ? 'info' : 'neutral'}>
                        {t.valueSource[v.value_source]}
                      </Badge>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      <div className={cn(v.gain.startsWith('-') ? 'text-negative' : Number(v.gain) > 0 && 'text-positive')}>
                        {formatAmount(v.gain, v.amount_currency)}
                      </div>
                      <Pct value={v.gain_pct} />
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{v.share_pct === null ? '–' : `${v.share_pct.replace('.', ',')}%`}</td>
                    <td className="py-2 text-right whitespace-nowrap">
                      {h && (
                        <Button variant="ghost" size="sm" onClick={() => onEdit(h)}>
                          {t.editAction}
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => remove(v.id)}>
                        {t.delete}
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export function PortfolioPage() {
  const [editing, setEditing] = useState<Holding | null>(null)
  const summary = usePortfolioSummary()
  const holdings = useHoldings()
  const s = summary.data

  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{t.title}</h1>
      <HoldingForm key={editing?.id ?? 'new'} editing={editing} onDone={() => setEditing(null)} />
      {summary.isLoading && <Spinner />}
      {summary.error && <ErrorMessage message={portfolioErrorMessage(summary.error)} />}
      {s && (
        <>
          {!s.prices_available && (
            <p role="status" className="rounded-md bg-warning/15 px-3 py-2 text-sm text-warning">
              {t.pricesUnavailable}
            </p>
          )}
          {s.fx_missing.length > 0 && (
            <p role="status" className="rounded-md bg-warning/15 px-3 py-2 text-sm text-warning">
              {t.fxMissing.replace('{currencies}', s.fx_missing.join(', '))}
            </p>
          )}
          <SummaryTiles s={s} />
          <HoldingsTable
            s={s}
            holdings={holdings.data ?? []}
            onEdit={(h) => {
              setEditing(h)
              window.scrollTo?.({ top: 0, behavior: 'smooth' })
            }}
          />
          <Allocation s={s} />
          <AdvisorPanel
            holdings={s.holdings.map((v): AdviceHoldingIn => ({
              symbol: v.symbol,
              asset_class: v.asset_class,
              quantity: v.quantity,
              // Not converted to PLN (missing FX rate): the advisor must not treat it as PLN.
              current_value: v.converted ? v.current_value : null,
            }))}
          />
        </>
      )}
    </>
  )
}
