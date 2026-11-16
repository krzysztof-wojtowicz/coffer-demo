import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import type { components } from '../../api/schema'
import { apiFetch } from '../../lib/apiFetch'
import { pl } from '../../i18n/pl'
import { validationText } from '../../lib/errors'
import { parseSse, type SseEvent } from './sse'

type S = components['schemas']
export type AgentStatus = S['AgentStatusOut']
export type ActionInfo = S['ActionInfoOut']
export type ParamSpec = S['ParamSpec']
export type ActionRunResult = S['ActionRunOut']
export type Report = S['ActionReport']
export type SuggestionItem = S['SuggestionOut']
export type RunListItem = S['AgentRunListItem']
export type RunDetail = S['AgentRunOut']

export async function fetchAgentStatus(signal?: AbortSignal): Promise<AgentStatus | null> {
  try {
    const res = await apiFetch('/api/agent/status', { credentials: 'include', signal })
    if (!res.ok) return null
    const data = await res.json()
    if (data && typeof data.available === 'boolean' && typeof data.provider === 'string') {
      return data as AgentStatus
    }
    return null
  } catch {
    return null
  }
}

export type StepEvent = { index: number; kind: string; name: string; status: string; duration_ms: number }

export type StreamHandlers = {
  onStatus?: (message: string) => void
  onStep?: (step: StepEvent) => void
}

/** Thrown for an SSE `error` event (or a failed HTTP response); message is Polish and user-facing. */
export class StreamError extends Error {
  fieldErrors: Record<string, string>
  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.fieldErrors = fieldErrors
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string; type?: string }

/** Maps a FastAPI 422 `detail` array to per-field Polish messages (body.params.<field>) and a form-level rest. */
export function mapValidationDetail(detail: unknown): { fields: Record<string, string>; general: string | null } {
  const fields: Record<string, string> = {}
  const general: string[] = []
  if (!Array.isArray(detail)) return { fields, general: null }
  for (const d of detail as ValidationItem[]) {
    const text =
      d.type === 'value_error' || d.type === 'assertion_error'
        ? (d.msg ?? '').replace(/^(Value|Assertion) error, /, '')
        : pl.assistant.fieldMessages[d.type ?? ''] ?? validationText(d.type ?? '')
    const loc = d.loc ?? []
    const i = loc.indexOf('params')
    const field = i >= 0 && loc.length > i + 1 ? String(loc[i + 1]) : null
    if (field) fields[field] = text
    else general.push(text)
  }
  return { fields, general: general.length ? general.join(' ') : null }
}

/** Runs an action over SSE and resolves with the final result. */
export async function streamAction(
  actionId: string,
  params: Record<string, unknown>,
  signal: AbortSignal,
  handlers: StreamHandlers = {},
): Promise<ActionRunResult> {
  const res = await apiFetch(`/api/agent/actions/${encodeURIComponent(actionId)}/run`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ params }),
    signal,
  })
  if (!res.ok || !res.body) {
    let detail: unknown
    try {
      detail = ((await res.json()) as { detail?: unknown }).detail
    } catch {
      detail = undefined
    }
    if (Array.isArray(detail)) {
      const { fields, general } = mapValidationDetail(detail)
      throw new StreamError(general ?? pl.assistant.formErrors, fields)
    }
    throw new StreamError(typeof detail === 'string' ? detail : pl.assistant.runFailed)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ActionRunResult | null = null
  let failure: string | null = null
  const handle = (events: SseEvent[]) => {
    for (const ev of events) {
      let data: unknown
      try {
        data = JSON.parse(ev.data)
      } catch {
        continue
      }
      if (ev.event === 'status') {
        const d = data as { message?: string } | string
        handlers.onStatus?.(typeof d === 'string' ? d : (d.message ?? ''))
      } else if (ev.event === 'step') {
        handlers.onStep?.(data as StepEvent)
      } else if (ev.event === 'result') {
        result = data as ActionRunResult
      } else if (ev.event === 'error') {
        const d = data as { detail?: string } | string
        failure = typeof d === 'string' ? d : (d.detail ?? pl.assistant.runFailed)
      }
    }
  }
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    const parsed = parseSse(decoder.decode(value, { stream: true }), buffer)
    buffer = parsed.rest
    handle(parsed.events)
  }
  handle(parseSse('\n\n', buffer).events)
  if (failure) throw new StreamError(failure)
  if (!result) throw new StreamError(pl.assistant.runFailed)
  return result
}

async function getJson<T>(url: string): Promise<T> {
  const res = await apiFetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as T
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  }
  return u.toString()
}

export function useActions() {
  return useQuery({
    queryKey: ['agent', 'actions'],
    queryFn: () => getJson<ActionInfo[]>('/api/agent/actions'),
    staleTime: 5 * 60_000,
  })
}

export type SuggestionFilters = {
  action: string
  source: string
  date_from: string
  date_to: string
  q: string
  order: 'asc' | 'desc'
}

export const SUGGESTIONS_PAGE = 5

export function useSuggestions(filters: SuggestionFilters) {
  return useInfiniteQuery({
    queryKey: ['agent', 'suggestions', filters],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      getJson<S['SuggestionListOut']>(
        `/api/agent/suggestions?${qs({ ...filters, limit: SUGGESTIONS_PAGE, offset: pageParam })}`,
      ),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0)
      return loaded < last.total && last.items.length > 0 ? loaded : undefined
    },
  })
}

export type RunSort = 'created_at' | 'duration_ms' | 'cost_usd' | 'tokens'

export type RunFilters = {
  action: string
  status: string
  provider: string
  date_from: string
  date_to: string
  sort: RunSort
  order: 'asc' | 'desc'
  page: number
}

export const RUNS_PAGE = 20

export function useRuns(f: RunFilters) {
  const { page, ...rest } = f
  return useQuery({
    queryKey: ['agent', 'runs', f],
    queryFn: () =>
      getJson<S['AgentRunListOut']>(
        `/api/agent/runs?${qs({ ...rest, limit: RUNS_PAGE, offset: (page - 1) * RUNS_PAGE })}`,
      ),
  })
}

export function useRun(id: number) {
  return useQuery({
    queryKey: ['agent', 'run', id],
    queryFn: () => getJson<RunDetail>(`/api/agent/runs/${id}`),
  })
}
