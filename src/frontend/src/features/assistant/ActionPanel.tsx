import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { ErrorMessage } from '../../components/ErrorMessage'
import { cn } from '../../lib/cn'
import { pl } from '../../i18n/pl'
import { ActionForm, buildParams, initialValue, validateParams, type FormErrors } from './ActionForm'
import { ActionReport } from './ActionReport'
import { actionLabel } from './labels'
import { AiStatusBadge } from './parts'
import {
  fetchAgentStatus,
  StreamError,
  streamAction,
  useActions,
  type ActionRunResult,
  type AgentStatus,
  type StepEvent,
} from './queries'
import { RunProgress } from './RunProgress'

const A = pl.assistant

type RunState =
  | { phase: 'idle' }
  | { phase: 'running'; steps: StepEvent[]; status: string | null }
  | { phase: 'done'; result: ActionRunResult }
  | { phase: 'error'; message: string; steps: StepEvent[] }
  | { phase: 'cancelled' }

/** One AI panel: pick an action from the catalogue, fill the generated form, watch it run. */
export function ActionPanel() {
  const actions = useActions()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [agent, setAgent] = useState<AgentStatus | null>(null)
  const [errors, setErrors] = useState<FormErrors>({})
  const [state, setState] = useState<RunState>({ phase: 'idle' })
  const ctl = useRef<AbortController | null>(null)

  useEffect(() => {
    const c = new AbortController()
    void fetchAgentStatus(c.signal).then((s) => {
      if (!c.signal.aborted) setAgent(s)
    })
    return () => c.abort()
  }, [])
  useEffect(() => () => ctl.current?.abort(), [])

  const selectedId = params.get('action')
  const selected = actions.data?.find((a) => a.id === selectedId) ?? null
  const values = Object.fromEntries(
    (selected?.params ?? []).map((s) => [s.name, initialValue(s, params.get(s.name))]),
  )

  const pick = (id: string) => {
    ctl.current?.abort()
    setErrors({})
    setState({ phase: 'idle' })
    setParams({ action: id }, { replace: true })
  }
  const change = (name: string, value: string) => {
    const next = new URLSearchParams(params)
    next.set(name, value)
    setParams(next, { replace: true })
    setErrors((e) => ({ ...e, [name]: '' }))
  }

  const run = async () => {
    if (!selected) return
    const errs = validateParams(selected.params, values)
    setErrors(errs)
    if (Object.values(errs).some(Boolean)) return
    const c = new AbortController()
    ctl.current = c
    const steps: StepEvent[] = []
    setState({ phase: 'running', steps: [], status: null })
    try {
      const result = await streamAction(selected.id, buildParams(selected.params, values), c.signal, {
        onStatus: (message) =>
          setState((s) => (s.phase === 'running' ? { ...s, status: message } : s)),
        onStep: (step) => {
          steps.push(step)
          setState((s) => (s.phase === 'running' ? { ...s, steps: [...steps] } : s))
        },
      })
      setState({ phase: 'done', result })
      void qc.invalidateQueries({ queryKey: ['agent', 'suggestions'] })
      void qc.invalidateQueries({ queryKey: ['agent', 'runs'] })
    } catch (e) {
      if (c.signal.aborted) {
        setState({ phase: 'cancelled' })
        return
      }
      if (e instanceof StreamError && Object.keys(e.fieldErrors).length > 0) {
        const known = new Set(selected.params.map((p) => p.name))
        const entries = Object.entries(e.fieldErrors)
        setErrors(Object.fromEntries(entries.filter(([k]) => known.has(k))))
        const extra = entries.filter(([k]) => !known.has(k)).map(([, m]) => m)
        const general = e.message === A.formErrors ? [] : [e.message]
        const text = [...general, ...extra].join(' ')
        setState(text ? { phase: 'error', message: text, steps } : { phase: 'idle' })
        return
      }
      setState({ phase: 'error', message: e instanceof Error ? e.message : A.runFailed, steps })
    }
  }
  const cancel = () => ctl.current?.abort()
  const running = state.phase === 'running'

  return (
    <Card title={A.title} actions={<AiStatusBadge status={agent} />}>
      {actions.isLoading && <p className="text-muted">{A.loadingActions}</p>}
      {actions.isError && <ErrorMessage message={pl.common.genericError} />}
      {actions.data?.length === 0 && <p className="text-muted">{A.noActions}</p>}
      {actions.data && actions.data.length > 0 && (
        <>
          <p className="mb-2 text-sm text-muted">{A.pickAction}</p>
          <div role="group" aria-label={A.actionsAria} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {actions.data.map((a) => {
              const active = a.id === selectedId
              return (
                <button
                  key={a.id}
                  type="button"
                  aria-pressed={active}
                  disabled={running}
                  onClick={() => pick(a.id)}
                  className={cn(
                    'cursor-pointer rounded-lg border p-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60',
                    active
                      ? 'border-accent bg-accent/10'
                      : 'border-border bg-surface-2 hover:border-accent/60',
                  )}
                >
                  <span className="block text-sm font-semibold text-text">
                    {actionLabel(a.id) !== a.id ? actionLabel(a.id) : a.name}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">{a.description}</span>
                  <span className="mt-2 flex flex-wrap gap-1">
                    {a.uses_user_data && <Badge tone="success">{A.usesUserData}</Badge>}
                    {a.uses_internet && <Badge tone="info">{A.usesInternet}</Badge>}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
      {selected && (
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <ActionForm
            specs={selected.params}
            values={values}
            errors={errors}
            running={running}
            onChange={change}
            onSubmit={() => void run()}
            onCancel={cancel}
          />
          {state.phase === 'running' && <RunProgress steps={state.steps} status={state.status ?? A.running} />}
          {state.phase === 'error' && (
            <RunProgress steps={state.steps} status={null} error={state.message} />
          )}
          {state.phase === 'cancelled' && <p className="text-sm text-muted">{A.cancelled}</p>}
          {state.phase === 'done' && (
            <ActionReport
              report={state.result.report}
              source={state.result.source}
              aiStatus={state.result.ai_status}
              runId={state.result.run_id}
              action={state.result.action}
            />
          )}
        </div>
      )}
    </Card>
  )
}
