import { Badge } from '../../components/ui/Badge'
import { pl } from '../../i18n/pl'
import type { components } from '../../api/schema'

type Rationale = components['schemas']['RationaleItemOut']

export function formatSeconds(ms: number | null | undefined): string {
  if (ms == null) return '–'
  return `${(Math.round(ms / 100) / 10).toFixed(1).replace('.', ',')} s`
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function runTone(status: string): 'success' | 'danger' | 'warning' | 'neutral' {
  if (status === 'ok') return 'success'
  if (status === 'invalid') return 'danger'
  if (status === 'unavailable') return 'warning'
  return 'neutral'
}

const sourceTone = { budget: 'info', profile: 'success', portfolio: 'neutral' } as const

export function RationaleList({ items, risks }: { items: Rationale[]; risks: string[] }) {
  const a = pl.assistant
  return (
    <>
      <h3 className="font-semibold">{a.rationale}</h3>
      <ul className="list-disc space-y-1 pl-5">
        {items.map((r, i) => (
          <li key={i}>
            {r.claim} <Badge tone={sourceTone[r.refers_to]}>{a.sources[r.refers_to]}</Badge>{' '}
            <span className="tabular-nums text-muted">{r.value}</span>
          </li>
        ))}
      </ul>
      {risks.length > 0 && (
        <>
          <h3 className="mt-3 font-semibold">{a.risks}</h3>
          <ul className="list-disc pl-5">
            {risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}
