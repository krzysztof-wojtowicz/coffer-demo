import { Link } from 'react-router-dom'
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { Money } from '../../components/Money'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import type { components } from '../../api/schema'
import { RationaleList } from './parts'
import { pl } from '../../i18n/pl'
import { fetchAgentStatus, streamSurplus, type AgentStatus } from './queries'
import { assistantReducer, initialAssistantState } from './state'

type Summary = components['schemas']['MonthSummaryOut']

function StatusBadge({ status }: { status: AgentStatus | null }) {
  if (!status) return null
  if (status.provider === 'none') return <Badge tone="neutral">{pl.assistant.statusOff}</Badge>
  if (status.available) {
    return <Badge tone="success">{pl.assistant.statusAvailable(status.model ?? '')}</Badge>
  }
  return <Badge tone="warning">{pl.assistant.statusUnavailable}</Badge>
}

function DataDisclosure({ summary, provider }: { summary: Summary; provider?: string }) {
  const a = pl.assistant
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-accent">{a.dataTitle}</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>
          {a.dataMonth}: {summary.month}
        </li>
        <li>
          {a.dataIncome}: <Money value={summary.income} />
        </li>
        <li>
          {a.dataExpenses}: <Money value={summary.expenses} />
        </li>
        <li>
          {a.dataSurplus}: <Money value={summary.surplus} />
        </li>
        <li>
          {a.dataByCategory}:
          <ul className="list-[circle] pl-5">
            {summary.by_category.map((c) => (
              <li key={c.category_id}>
                {c.category_name}: <Money value={c.expenses} />
              </li>
            ))}
          </ul>
        </li>
      </ul>
      <p className="mt-2 text-muted">{a.dataPrivacy(provider)}</p>
    </details>
  )
}

export function AssistantPanel({ month, summary }: { month: string; summary: Summary }) {
  const [state, dispatch] = useReducer(assistantReducer, initialAssistantState)
  const [agent, setAgent] = useState<AgentStatus | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const a = pl.assistant
  const noSurplus = summary.surplus === '0.00'

  useEffect(() => {
    const ctl = new AbortController()
    void fetchAgentStatus(ctl.signal).then((s) => {
      if (!ctl.signal.aborted) setAgent(s)
    })
    return () => ctl.abort()
  }, [])

  // Zmiana miesiąca (i odmontowanie) przerywa żądanie i czyści panel.
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      abortRef.current = null
      dispatch({ type: 'reset' })
    }
  }, [month])

  useEffect(() => {
    if (state.status !== 'loading') return
    setElapsed(0)
    const t0 = Date.now()
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000)
    return () => clearInterval(id)
  }, [state.status])

  const run = useCallback(() => {
    abortRef.current?.abort()
    const ctl = new AbortController()
    abortRef.current = ctl
    dispatch({ type: 'start' })
    streamSurplus(month, ctl.signal, (message) => {
      if (!ctl.signal.aborted) dispatch({ type: 'progress', message })
    })
      .then((response) => {
        if (!ctl.signal.aborted) dispatch({ type: 'success', response })
      })
      .catch(() => {
        if (!ctl.signal.aborted) dispatch({ type: 'failure' })
      })
  }, [month])

  const cancel = () => {
    abortRef.current?.abort()
    abortRef.current = null
    dispatch({ type: 'cancel' })
  }
  const clear = () => dispatch({ type: 'reset' })

  let body
  if (state.status === 'loading') {
    body = (
      <div className="space-y-2">
        <ul className="space-y-1" aria-live="polite">
          {state.steps.map((step, i) => {
            const current = i === state.steps.length - 1
            return (
              <li key={i} className="flex items-center gap-2">
                {current ? (
                  <Spinner />
                ) : (
                  <span aria-hidden="true" className="text-positive">
                    ✓
                  </span>
                )}
                <span className={current ? '' : 'text-muted'}>{step}</span>
                {current && <span className="tabular-nums text-muted">{a.seconds(elapsed)}</span>}
              </li>
            )
          })}
          {state.steps.length === 0 && (
            <li className="flex items-center gap-2">
              <Spinner />
              <span>{a.loading}</span>
              <span className="tabular-nums text-muted">{a.seconds(elapsed)}</span>
            </li>
          )}
        </ul>
        <p className="text-sm text-muted">{a.loadingHint}</p>
        <Button variant="secondary" size="sm" onClick={cancel}>
          {a.cancel}
        </Button>
      </div>
    )
  } else if (state.status === 'ok') {
    const s = state.suggestion
    const secs = (Math.round((s.duration_ms ?? 0) / 100) / 10).toFixed(1).replace('.', ',')
    const time = new Date(s.generated_at).toLocaleTimeString('pl-PL', {
      hour: '2-digit',
      minute: '2-digit',
    })
    body = (
      <div className="space-y-3">
        <div className="rounded-lg border border-accent/40 bg-accent-soft p-4">
          <p>{s.summary}</p>
          <div className="mt-3">
            <RationaleList items={s.rationale} risks={s.risks} />
          </div>
          <p className="mt-3 flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-2 text-sm text-warning">
            <span aria-hidden="true">ⓘ</span>
            <span>{s.disclaimer}</span>
          </p>
          <p className="mt-3 text-xs text-muted">
            {a.footer(s.model, secs, time)} · {s.profile_used ? a.withProfile : a.withoutProfile}
            {state.runId != null && (
              <>
                {' · '}
                <Link className="text-accent hover:underline" to={`/assistant/runs/${state.runId}`}>
                  {a.showTrace}
                </Link>
              </>
            )}
          </p>
          {!s.profile_used && (
            <p className="mt-2 text-sm">
              {a.profileNudge}.{' '}
              <Link className="text-accent hover:underline" to="/profile">
                {a.profileLink}
              </Link>
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={run}>
            {a.regenerate}
          </Button>
          <Button variant="ghost" size="sm" onClick={clear}>
            {a.clear}
          </Button>
        </div>
      </div>
    )
  } else if (state.status === 'limited') {
    body = <p className="rounded-md bg-warning/10 p-3 text-warning">{a.limited}</p>
  } else if (state.status === 'unavailable') {
    body = (
      <div className="space-y-3">
        <p className="rounded-md bg-warning/10 p-3 text-warning">{a.unavailable}</p>
        <Button variant="secondary" size="sm" onClick={run}>
          {a.retry}
        </Button>
      </div>
    )
  } else {
    const showNoSurplus = state.status === 'no_surplus' || noSurplus
    body = (
      <div className="space-y-3">
        <p className="text-text">{a.description}</p>
        <StatusBadge status={agent} />
        <DataDisclosure summary={summary} provider={agent?.provider} />
        <div>
          <Button onClick={run} disabled={showNoSurplus}>
            {a.ask}
          </Button>
        </div>
        {showNoSurplus && <p className="text-sm text-muted">{a.noSurplus}</p>}
        {!showNoSurplus && agent && agent.provider !== 'none' && !agent.available && (
          <p className="text-sm text-warning">{a.unavailableHint}</p>
        )}
      </div>
    )
  }

  return <Card title={a.title}>{body}</Card>
}
