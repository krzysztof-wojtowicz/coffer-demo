import { useEffect, useRef, useState } from 'react'
import { AllocationChart, targetSlices } from './AllocationChart'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { Spinner } from '../../components/ui/Spinner'
import { Stat } from '../../components/ui/Stat'
import { pl } from '../../i18n/pl'
import { formatMoney, formatPct } from '../../lib/format'
import { HoldingForm, portfolioErrorMessage } from './HoldingForm'
import {
  useDeleteHolding,
  formatAsOf,
  isStale,
  useHoldings,
  usePortfolioSummary,
  type Holding,
  type PortfolioSummary,
} from './queries'

const t = pl.portfolio

function GainPct({ value }: { value: string | null }) {
  if (value === null) return <span className="text-muted">–</span>
  return <Signed kind="pct" value={value} />
}

function SummaryTiles({ s }: { s: PortfolioSummary }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card>
        <Stat label={t.totalValue} value={<Money value={s.total_value} />} />
      </Card>
      <Card>
        <Stat label={t.totalCost} value={<Money value={s.total_cost} />} />
      </Card>
      <Card>
        <Stat
          label={t.totalGain}
          value={<Signed value={s.total_gain} />}
          delta={<GainPct value={s.total_gain_pct} />}
        />
      </Card>
    </div>
  )
}

function Allocation({ s }: { s: PortfolioSummary }) {
  return (
    <Card title={t.allocation}>
      {s.allocation.length > 0 ? (
        <AllocationChart allocation={s.allocation} target={s.target ?? null} />
      ) : s.target ? (
        // Profile but nothing valued yet: show the target alone, without a comparison.
        <AllocationChart
          allocation={targetSlices(s.target.classes.map((c) => ({ asset_class: c.asset_class, share_pct: c.target_pct })))}
          targetOnly
        />
      ) : (
        <p className="text-muted">{t.noAllocation}</p>
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
                    <td className="py-2 pr-3">{pl.assetClass[v.asset_class]}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{v.quantity.replace('.', ',')}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{formatMoney(v.cost_basis, v.amount_currency)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      <div>{formatMoney(v.current_value, v.amount_currency)}</div>
                      <Badge tone={v.value_source === 'market' ? 'info' : 'neutral'}>
                        {t.valueSource[v.value_source]}
                      </Badge>
                      {v.as_of && isStale(v.as_of) && (
                        <div className="mt-0.5 text-xs text-warning">{t.priceFrom(formatAsOf(v.as_of))}</div>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      <div>
                        <Signed value={v.gain} currency={v.amount_currency} />
                      </div>
                      <GainPct value={v.gain_pct} />
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{formatPct(v.share_pct)}</td>
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
  // `formOpen` shows the form; `editing` (when set) fills it with a holding.
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Holding | null>(null)
  const formRef = useRef<HTMLDivElement>(null)
  const summary = usePortfolioSummary()
  const holdings = useHoldings()
  const s = summary.data

  useEffect(() => {
    if (formOpen) formRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  }, [formOpen, editing])

  const closeForm = () => {
    setFormOpen(false)
    setEditing(null)
  }

  return (
    <>
      <h1 className="text-2xl font-semibold text-text">{t.title}</h1>
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            {s.prices_as_of ? (
              <p className="text-sm text-muted">{t.pricesAsOf(formatAsOf(s.prices_as_of))}</p>
            ) : (
              <span />
            )}
          </div>
          <SummaryTiles s={s} />
          <Allocation s={s} />
          <HoldingsTable
            s={s}
            holdings={holdings.data ?? []}
            onEdit={(h) => {
              setEditing(h)
              setFormOpen(true)
            }}
          />
        </>
      )}
      {!formOpen && (
        <div>
          <Button variant="secondary" onClick={() => setFormOpen(true)}>
            {t.addButton}
          </Button>
        </div>
      )}
      {formOpen && (
        <div ref={formRef}>
          <HoldingForm key={editing?.id ?? 'new'} editing={editing} onDone={closeForm} />
        </div>
      )}
    </>
  )
}
