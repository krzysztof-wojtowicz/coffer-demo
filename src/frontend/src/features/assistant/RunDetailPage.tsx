import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import {
  actionDisplay,
  formatCost,
  formatDateTime,
  formatMs,
  optionLabel,
  providerLabel,
  runStatusLabel,
  runTone,
} from './labels'
import { Pre } from './parts'
import { useActions, useRun } from './queries'
import { RunTimeline } from './RunTimeline'

const A = pl.assistant

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <details className="rounded-md border border-border bg-surface-2 p-3">
      <summary className="cursor-pointer font-semibold">
        {title} <span className="font-normal text-muted">({count})</span>
      </summary>
      <div className="mt-3 space-y-3">{count === 0 ? <p className="text-muted">{A.runNone}</p> : children}</div>
    </details>
  )
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-md bg-surface-2 p-2.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-sm font-semibold tabular-nums text-text">{children}</dd>
    </div>
  )
}

export function RunDetailPage() {
  const { id } = useParams()
  const runId = Number(id)
  const run = useRun(runId)
  const actions = useActions()
  const labelOf = (name: string) =>
    actions.data?.find((a) => a.id === run.data?.action)?.params.find((p) => p.name === name)?.label ?? name

  if (run.isLoading) return <p>{pl.common.loading}</p>
  if (run.isError || !run.data) {
    return (
      <Card title={A.runTitle}>
        <ErrorMessage message={A.runNotFound} />
        <Link className="text-accent hover:underline" to="/assistant">
          {A.runBack}
        </Link>
      </Card>
    )
  }
  const r = run.data
  const legacy = r.steps.length === 0
  const params = Object.entries(r.params ?? {})
  return (
    <Card
      title={A.runTitle}
      actions={
        <Link className="text-sm text-accent hover:underline" to="/assistant">
          {A.runBack}
        </Link>
      }
    >
      <p className="mb-3 text-sm text-muted">{A.runTraceHint}</p>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-base font-semibold">{actionDisplay(r.action)}</span>
        <Badge tone={runTone(r.status)}>{runStatusLabel(r.status)}</Badge>
        <span className="text-xs text-muted">{formatDateTime(r.created_at)}</span>
      </div>
      <dl className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label={A.runProvider}>{providerLabel(r.provider)}</Stat>
        <Stat label={A.runModel}>{r.model ?? '—'}</Stat>
        <Stat label={A.runTokensIn}>{r.input_tokens ?? '—'}</Stat>
        <Stat label={A.runTokensOut}>{r.output_tokens ?? '—'}</Stat>
        <Stat label={A.runCost}>{formatCost(r.cost_usd)}</Stat>
        <Stat label={A.runTotalTime}>{formatMs(r.duration_ms)}</Stat>
        <Stat label={A.runPrompt}>{r.prompt_version}</Stat>
        <Stat label={A.colTools}>{r.tool_calls_count}</Stat>
      </dl>
      {params.length > 0 && (
        <div className="mb-3 text-sm">
          <h3 className="mb-1 font-semibold">{A.runParams}</h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            {params.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{labelOf(k)}</dt>
                <dd>{optionLabel(k, String(v))}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {r.error && <ErrorMessage message={`${A.runError}: ${r.error}`} />}
      <div className="space-y-3">
        {legacy ? (
          <>
            <p className="text-sm text-muted">{A.runLegacyHint}</p>
            <Section title={A.runToolCalls} count={r.tool_calls.length}>
              {r.tool_calls.map((c, i) => (
                <div key={i} className="space-y-1">
                  <p className="font-mono text-sm">{String(c.name ?? '')}</p>
                  <p className="text-xs text-muted">{A.runArguments}</p>
                  <Pre>{c.arguments ?? {}}</Pre>
                  <p className="text-xs text-muted">{A.runResult}</p>
                  <Pre>{c.output ?? null}</Pre>
                </div>
              ))}
            </Section>
            <Section title={A.runRaw} count={r.raw_outputs.length}>
              {r.raw_outputs.map((o, i) => (
                <Pre key={i}>{o}</Pre>
              ))}
            </Section>
            <Section title={A.runErrors} count={r.validation_errors.length}>
              {r.validation_errors.map((e, i) => (
                <Pre key={i}>{e}</Pre>
              ))}
            </Section>
          </>
        ) : (
          <section>
            <h3 className="mb-2 font-semibold">{A.runTimeline}</h3>
            <RunTimeline steps={r.steps} totalMs={r.duration_ms ?? null} />
          </section>
        )}
        <Section title={A.runPrompts} count={r.messages.length}>
          {r.messages.map((m, i) => (
            <div key={i}>
              <Badge>{String(m.role ?? '')}</Badge>
              <Pre>{m.content ?? m}</Pre>
            </div>
          ))}
        </Section>
      </div>
    </Card>
  )
}
