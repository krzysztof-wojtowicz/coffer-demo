import { useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { cn } from '../../lib/cn'
import { pl } from '../../i18n/pl'
import { formatCost, formatMs, formatTokens, providerLabel, toolLabel } from './labels'
import { Pre } from './parts'

const A = pl.assistant

type Step = Record<string, unknown>

const ICONS: Record<string, string> = {
  tool: 'N',
  llm: 'M',
  validation: 'W',
  fallback: 'R',
  limit: 'L',
  error: '!',
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)

function title(s: Step): string {
  const kind = String(s.kind ?? '')
  const name = String(s.name ?? '')
  if (kind === 'tool') return toolLabel(name)
  return A.stepKinds[kind] ?? name
}

function Detail({ s }: { s: Step }) {
  const kind = String(s.kind ?? '')
  if (kind === 'tool') {
    return (
      <div className="space-y-1">
        <p className="font-mono text-xs text-muted">
          {String(s.name ?? '')}
          {str(s.origin) ? ` · ${A.stepOrigin[String(s.origin)] ?? s.origin}` : ''}
        </p>
        <p className="text-xs text-muted">{A.runArguments}</p>
        <Pre>{s.arguments ?? {}}</Pre>
        <p className="text-xs text-muted">{A.runResult}</p>
        <Pre>{s.output ?? null}</Pre>
        {str(s.error) && <p className="text-xs text-negative">{String(s.error)}</p>}
      </div>
    )
  }
  if (kind === 'llm') {
    return (
      <div className="space-y-1">
        <p className="text-xs text-muted">
          {providerLabel(str(s.provider))} · {str(s.model) ?? '—'}
          {num(s.attempt) != null ? ` · ${A.stepAttempt(num(s.attempt) as number)}` : ''}
          {' · '}
          {A.colTokens}: {formatTokens(num(s.input_tokens), num(s.output_tokens))}
          {' · '}
          {A.colCost}: {formatCost(str(s.cost_usd))}
        </p>
        <p className="text-xs text-muted">{A.runOutput}</p>
        <Pre>{s.output ?? ''}</Pre>
      </div>
    )
  }
  if (kind === 'validation') {
    const errs = Array.isArray(s.errors) ? s.errors : []
    return errs.length === 0 ? (
      <p className="text-xs text-muted">{A.runNone}</p>
    ) : (
      <ul className="list-disc pl-5 text-xs text-negative">
        {errs.map((e, i) => (
          <li key={i}>{String(e)}</li>
        ))}
      </ul>
    )
  }
  if (kind === 'fallback') {
    const reason = str(s.reason)
    return (
      <p className="text-xs text-muted">
        {A.stepReason}: {reason ? (A.runStatus[reason] ?? reason) : '—'}
      </p>
    )
  }
  return <Pre>{s}</Pre>
}

/** Vertical timeline of agent run steps; each step expands to its details. */
export function RunTimeline({ steps, totalMs }: { steps: Step[]; totalMs: number | null }) {
  const [open, setOpen] = useState<Set<number>>(new Set())
  const toggle = (i: number) =>
    setOpen((p) => {
      const n = new Set(p)
      if (n.has(i)) n.delete(i)
      else n.add(i)
      return n
    })
  const end = Math.max(
    totalMs ?? 0,
    ...steps.map((s) => (num(s.started_ms) ?? 0) + (num(s.duration_ms) ?? 0)),
    1,
  )
  return (
    <ol aria-label={A.runTimeline} className="relative space-y-2 border-l-2 border-border pl-4">
      {steps.map((s, i) => {
        const kind = String(s.kind ?? '')
        const failed = s.status === 'error'
        const start = num(s.started_ms) ?? 0
        const dur = num(s.duration_ms) ?? 0
        const expanded = open.has(i)
        return (
          <li key={i} className="relative">
            <span
              aria-hidden="true"
              className="absolute -left-[26px] top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-surface text-[10px]"
            >
              {ICONS[kind] ?? '•'}
            </span>
            <button
              type="button"
              aria-expanded={expanded}
              onClick={() => toggle(i)}
              className="w-full cursor-pointer rounded-md border border-border bg-surface-2 p-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <span className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-text">{title(s)}</span>
                <Badge tone={failed ? 'danger' : 'success'}>
                  {A.stepStatus[String(s.status ?? 'ok')] ?? String(s.status)}
                </Badge>
                <span className="ml-auto tabular-nums text-xs text-muted">{formatMs(dur)}</span>
              </span>
              <span
                className="mt-1.5 block h-1.5 rounded bg-bg"
                role="img"
                aria-label={`${formatMs(dur)}`}
              >
                <span
                  className={cn('block h-1.5 rounded', failed ? 'bg-negative' : 'bg-accent')}
                  style={{
                    marginLeft: `${(start / end) * 100}%`,
                    width: `${Math.max((dur / end) * 100, 1.5)}%`,
                  }}
                />
              </span>
            </button>
            {expanded && (
              <div className="mt-1 rounded-md border border-border p-2.5">
                <Detail s={s} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
