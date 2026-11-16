import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { pl } from '../../i18n/pl'
import { formatMoney } from '../../lib/money'
import { useSetLimit } from '../budget/queries'
import type { Report } from './queries'

const A = pl.assistant

type Proposal = { categoryId: number; name: string; amount: string }

export function proposalsFrom(report: Report): Proposal[] {
  const table = report.tables.find((t) => t.id === 'proposed_limits')
  if (!table) return []
  const out: Proposal[] = []
  for (const r of table.rows) {
    const id = Number(r.category_id)
    const amount = r.proposed_limit
    if (!Number.isInteger(id) || id <= 0 || !amount || !(Number(amount) > 0)) continue
    out.push({ categoryId: id, name: r.category ?? '', amount })
  }
  return out
}

/** Applies the budget_plan proposals via PUT /api/budget/limits/{id} after confirmation. */
export function ApplyLimits({ report }: { report: Report }) {
  const proposals = proposalsFrom(report)
  const setLimit = useSetLimit()
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  if (proposals.length === 0) return null

  const apply = async () => {
    setPending(true)
    const results = await Promise.allSettled(
      proposals.map((p) => setLimit.mutateAsync({ categoryId: p.categoryId, amount: p.amount })),
    )
    const ok = results.filter((r) => r.status === 'fulfilled').length
    const fail = results.length - ok
    setMsg(fail === 0 ? { ok: true, text: A.setLimitsOk(ok) } : { ok: false, text: A.setLimitsFail(ok, fail) })
    setPending(false)
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {A.setLimits}
      </Button>
      {msg && (
        <p role={msg.ok ? 'status' : 'alert'} className={msg.ok ? 'text-sm text-positive' : 'text-sm text-negative'}>
          {msg.text}
        </p>
      )}
      <ConfirmDialog
        open={open}
        title={A.setLimitsTitle}
        message={`${A.setLimitsMessage} ${proposals.map((p) => `${p.name}: ${formatMoney(p.amount)}`).join('; ')}`}
        confirmLabel={A.setLimitsConfirm}
        danger={false}
        pending={pending}
        onConfirm={() => void apply()}
        onCancel={() => setOpen(false)}
      />
    </div>
  )
}
