import { apiFetch } from '../../lib/apiFetch'
import { useQuery } from '@tanstack/react-query'
import type { components } from '../../api/schema'
import { parseSse, type SseEvent } from './sse'
import type { SurplusResponse } from './state'

export type AgentStatus = components['schemas']['AgentStatusOut']

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

export async function streamSurplus(
  month: string,
  signal: AbortSignal,
  onStatus: (message: string) => void,
): Promise<SurplusResponse> {
  const res = await apiFetch('/api/agent/surplus/stream', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ month }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: SurplusResponse | null = null
  const handle = (events: SseEvent[]) => {
    for (const ev of events) {
      if (ev.event === 'status') {
        const d = JSON.parse(ev.data) as { message?: string } | string
        onStatus(typeof d === 'string' ? d : (d.message ?? ''))
      } else if (ev.event === 'result') {
        result = JSON.parse(ev.data) as SurplusResponse
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
  // dokończ ewentualne ostatnie zdarzenie bez pustej linii na końcu
  handle(parseSse('\n\n', buffer).events)
  if (!result) throw new Error('Strumień zakończył się bez wyniku')
  return result
}

export type SuggestionItem = components['schemas']['SuggestionOut']
export type RunListItem = components['schemas']['AgentRunListItem']
export type RunDetail = components['schemas']['AgentRunOut']

async function getJson<T>(url: string): Promise<T> {
  const res = await apiFetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as T
}

export function useSuggestions() {
  return useQuery({
    queryKey: ['agent', 'suggestions'],
    queryFn: async () => {
      return getJson<SuggestionItem[]>('/api/agent/suggestions?limit=20')
    },
  })
}

export function useRuns() {
  return useQuery({
    queryKey: ['agent', 'runs'],
    queryFn: async () => {
      return getJson<RunListItem[]>('/api/agent/runs?limit=20')
    },
  })
}

export function useRun(id: number) {
  return useQuery({
    queryKey: ['agent', 'runs', id],
    queryFn: async () => {
      return getJson<RunDetail>(`/api/agent/runs/${id}`)
    },
  })
}
