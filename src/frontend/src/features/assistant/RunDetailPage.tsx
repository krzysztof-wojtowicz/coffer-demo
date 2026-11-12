import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import { formatDateTime, formatSeconds, runTone } from './parts'
import { useRun } from './queries'

const pretty = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2))

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <details className="rounded-md border border-border bg-surface-2 p-3">
      <summary className="cursor-pointer font-semibold">
        {title} <span className="font-normal text-muted">({count})</span>
      </summary>
      <div className="mt-3 space-y-3">{count === 0 ? <p className="text-muted">{pl.assistant.runNone}</p> : children}</div>
    </details>
  )
}

const Pre = ({ children }: { children: unknown }) => (
  <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-bg p-2 text-xs text-text">{pretty(children)}</pre>
)

export function RunDetailPage() {
  const a = pl.assistant
  const { id } = useParams()
  const runId = Number(id)
  const run = useRun(runId)

  if (run.isLoading) return <p>{pl.common.loading}</p>
  if (run.isError || !run.data) {
    return (
      <Card title={a.runTitle}>
        <ErrorMessage message={a.runNotFound} />
        <Link className="text-accent hover:underline" to="/assistant">
          {a.runBack}
        </Link>
      </Card>
    )
  }
  const r = run.data
  return (
    <Card title={a.runTitle} actions={<Link className="text-sm text-accent hover:underline" to="/assistant">{a.runBack}</Link>}>
      <p className="mb-3 text-sm text-muted">{a.runTraceHint}</p>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <Badge tone="info">{a.kind[r.task] ?? r.task}</Badge>
        <Badge tone={runTone(r.status)}>{a.runStatus[r.status] ?? r.status}</Badge>
        <span>{a.colAttempts}: {r.attempts}</span>
        <span>{a.runTokens}: {r.input_tokens ?? '–'} / {r.output_tokens ?? '–'}</span>
        <span>{a.colDuration}: {formatSeconds(r.duration_ms)}</span>
        <span>{a.runPrompt}: {r.prompt_version}</span>
        <span>{formatDateTime(r.created_at)}</span>
      </div>
      {r.error && <ErrorMessage message={`${a.runError}: ${r.error}`} />}
      <div className="space-y-3">
        <Section title={a.runMessages} count={r.messages.length}>
          {r.messages.map((m, i) => (
            <div key={i}>
              <Badge>{String(m.role ?? '')}</Badge>
              <Pre>{m.content ?? m}</Pre>
            </div>
          ))}
        </Section>
        <Section title={a.runToolCalls} count={r.tool_calls.length}>
          {r.tool_calls.map((c, i) => (
            <div key={i} className="space-y-1">
              <p className="font-mono text-sm">{String(c.name ?? '')}</p>
              <p className="text-xs text-muted">{a.runArguments}</p>
              <Pre>{JSON.stringify(c.arguments ?? {}, null, 2)}</Pre>
              <p className="text-xs text-muted">{a.runResult}</p>
              <Pre>{JSON.stringify(c.output ?? null, null, 2)}</Pre>
            </div>
          ))}
        </Section>
        <Section title={a.runRaw} count={r.raw_outputs.length}>
          {r.raw_outputs.map((o, i) => (
            <Pre key={i}>{o}</Pre>
          ))}
        </Section>
        <Section title={a.runErrors} count={r.validation_errors.length}>
          {r.validation_errors.map((e, i) => (
            <Pre key={i}>{e}</Pre>
          ))}
        </Section>
      </div>
    </Card>
  )
}
