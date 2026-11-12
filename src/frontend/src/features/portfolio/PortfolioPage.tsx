import { useState } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { HoldingForm, portfolioErrorMessage } from './HoldingForm'
import {
  useDeleteHolding,
  useHoldings,
  usePortfolioSummary,
  type Holding,
  type PortfolioSummary,
} from './queries'

const t = pl.portfolio

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
  const [pendingId, setPendingId] = useState<number | null>(null)
  const remove = (id: number) => setPendingId(id)
  return (
    <Card title={t.holdings}>
      <ConfirmDialog
        open={pendingId !== null}
        title={t.delete}
        message={t.confirmDelete}
        confirmLabel={t.delete}
        cancelLabel={t.cancel}
        danger
        pending={del.isPending}
        onConfirm={() => {
          if (pendingId !== null) del.mutate(pendingId, { onSettled: () => setPendingId(null) })
        }}
        onCancel={() => setPendingId(null)}
      />
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
        </>
      )}
    </>
  )
}
