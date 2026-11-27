import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AllocationChart, targetSlices } from './AllocationChart'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Signed } from '../../components/Signed'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { Stat } from '../../components/ui/Stat'
import { pl } from '../../i18n/pl'
import { formatMoney, formatPct } from '../../lib/format'
import {
  defaultPositionOptions,
  filterAndSortPositions,
  type Position,
  type PositionListOptions,
  type PositionSortDir,
  type PositionSortKey,
} from './list'
import { HoldingForm, portfolioErrorMessage } from './HoldingForm'
import {
  ASSET_CLASSES,
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

const dash = <span className="text-muted">–</span>

function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-[8rem] flex-1 flex-col gap-1 lg:min-w-0">
      <span className="text-xs text-muted">{label}</span>
      {children}
    </div>
  )
}

function PositionRow({
  p,
  byId,
  open,
  onToggle,
  onEdit,
  onDelete,
}: {
  p: Position
  byId: Map<number, Holding>
  open: boolean
  onToggle: () => void
  onEdit: (h: Holding) => void
  onDelete: (id: number) => void
}) {
  return (
    <li className="border-b border-border/60">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="grid w-full grid-cols-[1.5rem_minmax(0,2fr)_repeat(5,minmax(0,1fr))] items-center gap-2 py-2 text-left text-sm hover:bg-surface-2/50"
      >
        <span aria-hidden className="text-muted">
          {open ? '▾' : '▸'}
        </span>
        <span className="min-w-0">
          <span className="block truncate">{p.name}</span>
          <span className="block text-xs text-muted">
            {p.symbol ? `${p.symbol} · ` : ''}
            {pl.assetClass[p.asset_class]} · {t.lots(p.lots.length)}
          </span>
        </span>
        <span className="text-right tabular-nums">
          <span className="block text-xs text-muted">{t.quantity}</span>
          {p.quantity.replace('.', ',')}
        </span>
        <span className="text-right tabular-nums">
          <span className="block text-xs text-muted">{t.cost}</span>
          {p.cost ? formatMoney(p.cost, 'PLN') : dash}
        </span>
        <span className="text-right tabular-nums">
          <span className="block text-xs text-muted">{t.value}</span>
          {p.value ? formatMoney(p.value, 'PLN') : dash}
        </span>
        <span className="text-right tabular-nums">
          <span className="block text-xs text-muted">{t.gain}</span>
          {p.gain ? <Signed value={p.gain} /> : dash}
          <span className="block">
            <GainPct value={p.gain_pct} />
          </span>
        </span>
        <span className="text-right tabular-nums">
          <span className="block text-xs text-muted">{t.share}</span>
          {p.share_pct ? formatPct(p.share_pct) : dash}
        </span>
      </button>
      {open && (
        <ul aria-label={p.name} className="mb-2 ml-6 rounded bg-surface-2/40 px-3">
          {p.lots.map((l) => {
            const h = byId.get(l.holding_id)
            return (
              <li
                key={l.holding_id}
                className="grid grid-cols-[minmax(0,1fr)_repeat(5,minmax(0,1fr))_auto] items-center gap-2 border-b border-border/40 py-2 text-sm last:border-b-0"
              >
                <span><span className="block text-xs text-muted">{t.purchaseDate}</span>{l.purchase_date ?? <span className="text-muted">{t.noDate}</span>}</span>
                <span className="text-right tabular-nums"><span className="block text-xs text-muted">{t.quantity}</span>{l.quantity.replace('.', ',')}</span>
                <span className="text-right tabular-nums"><span className="block text-xs text-muted">{t.purchasePrice}</span>{formatMoney(l.purchase_price, l.currency)}</span>
                <span className="text-right tabular-nums"><span className="block text-xs text-muted">{t.cost}</span>{formatMoney(l.cost, l.currency)}</span>
                <span className="text-right tabular-nums">
                  <span className="block text-xs text-muted">{t.value}</span>
                  <span className="block">{formatMoney(l.value, l.currency)}</span>
                  <Badge tone={l.value_source === 'market' ? 'info' : 'neutral'}>{t.valueSource[l.value_source]}</Badge>
                  {l.as_of && isStale(l.as_of) && (
                    <span className="mt-0.5 block text-xs text-warning">{t.priceFrom(formatAsOf(l.as_of))}</span>
                  )}
                </span>
                <span className="text-right tabular-nums">
                  <span className="block text-xs text-muted">{t.gain}</span>
                  <Signed value={l.gain} currency={l.currency} />
                  <span className="block">
                    <GainPct value={l.gain_pct} />
                  </span>
                </span>
                <span className="whitespace-nowrap text-right">
                  {h && (
                    <Button variant="ghost" size="sm" onClick={() => onEdit(h)}>
                      {t.editAction}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => onDelete(l.holding_id)}>
                    {t.delete}
                  </Button>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}

function PositionsCard({
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
  const [opts, setOpts] = useState<PositionListOptions>(defaultPositionOptions)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const set = (patch: Partial<PositionListOptions>) => setOpts((o) => ({ ...o, ...patch }))
  const visible = useMemo(() => filterAndSortPositions([...s.positions], opts), [s.positions, opts])
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (!next.delete(key)) next.add(key)
      return next
    })
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
      {s.positions.length === 0 ? (
        <p className="text-muted">{t.empty}</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-end gap-2 lg:flex-nowrap">
            <FilterField label={t.filterClass}>
              <Select
                aria-label={t.filterClassLabel}
                variant="ghost"
                className="w-full"
                value={opts.assetClass ?? ''}
                onChange={(e) => set({ assetClass: e.target.value || null })}
              >
                <option value="">{t.filterClass}: {t.allClasses}</option>
                {ASSET_CLASSES.map((c) => (
                  <option key={c} value={c}>
                    {pl.assetClass[c]}
                  </option>
                ))}
              </Select>
            </FilterField>
            <FilterField label={t.search}>
              <Input
                aria-label={t.search}
                placeholder={t.searchPlaceholder}
                value={opts.query}
                onChange={(e) => set({ query: e.target.value })}
              />
            </FilterField>
            <FilterField label={t.sortBy}>
              <Select
                aria-label={t.sortBy}
                variant="ghost"
                className="w-full"
                value={opts.sortKey}
                onChange={(e) => set({ sortKey: e.target.value as PositionSortKey })}
              >
                <option value="value">{t.sortValue}</option>
                <option value="name">{t.sortName}</option>
                <option value="gain">{t.sortGain}</option>
                <option value="gain_pct">{t.sortGainPct}</option>
                <option value="date">{t.sortDate}</option>
              </Select>
            </FilterField>
            <FilterField label={t.sortDir}>
              <Select
                aria-label={t.sortDir}
                variant="ghost"
                className="w-full"
                value={opts.sortDir}
                onChange={(e) => set({ sortDir: e.target.value as PositionSortDir })}
              >
                <option value="desc">{t.sortDesc}</option>
                <option value="asc">{t.sortAsc}</option>
              </Select>
            </FilterField>
          </div>
          {visible.length === 0 ? (
            <p className="text-muted">{t.emptyFiltered}</p>
          ) : (
            <ul>
              {visible.map((p) => (
                <PositionRow
                  key={p.key}
                  p={p}
                  byId={byId}
                  open={expanded.has(p.key)}
                  onToggle={() => toggle(p.key)}
                  onEdit={onEdit}
                  onDelete={setPendingId}
                />
              ))}
            </ul>
          )}
        </>
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
      <div>
        <Button
          variant={formOpen ? 'primary' : 'secondary'}
          onClick={() => (formOpen ? closeForm() : setFormOpen(true))}
        >
          {t.addButton}
        </Button>
      </div>
      {formOpen && (
        <div ref={formRef}>
          <HoldingForm key={editing?.id ?? 'new'} editing={editing} onDone={closeForm} />
        </div>
      )}
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
          <PositionsCard
            s={s}
            holdings={holdings.data ?? []}
            onEdit={(h) => {
              setEditing(h)
              setFormOpen(true)
            }}
          />
        </>
      )}
    </>
  )
}
