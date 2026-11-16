import { pl } from '../../i18n/pl'
import { formatMs, toolLabel } from './labels'
import type { StepEvent } from './queries'

const A = pl.assistant

function stepName(s: StepEvent): string {
  return s.kind === 'tool' ? toolLabel(s.name) : (A.stepKinds[s.kind] ?? s.name)
}

/** Live progress: executed steps (from SSE `step` events) and the latest `status` message. */
export function RunProgress({
  steps,
  status,
  error,
}: {
  steps: StepEvent[]
  status: string | null
  error?: string | null
}) {
  return (
    <div aria-live="polite" className="space-y-2 text-sm">
      {error && (
        <p role="alert" className="rounded-md bg-negative/10 p-3 text-negative">
          {error}
        </p>
      )}
      {status && !error && <p className="text-muted">{status}</p>}
      {steps.length > 0 && (
        <ol aria-label={A.liveSteps} className="space-y-1">
          {steps.map((s) => (
            <li key={s.index} className="flex items-center justify-between gap-3 rounded bg-surface-2 px-2.5 py-1.5">
              <span>{stepName(s)}</span>
              <span className="tabular-nums text-xs text-muted">
                {s.status === 'error' ? `${A.stepFailed} · ` : ''}
                {formatMs(s.duration_ms)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
