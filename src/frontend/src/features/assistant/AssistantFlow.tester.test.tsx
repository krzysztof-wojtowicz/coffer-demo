import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AssistantPage } from './AssistantPage'

// Full flow from the contract (E5-10): pick action -> params -> SSE -> report -> history after reload.

const ACTIONS = [
  { id: 'portfolio_review', name: 'Analiza portfela', description: 'Przegląd portfela', params: [], tools: [], uses_user_data: true, uses_internet: false },
  {
    id: 'purchase_impact',
    name: 'Wpływ zakupu na portfel',
    description: 'Co zmieni zakup',
    params: [{ name: 'amount', label: 'Kwota', kind: 'amount', required: true, default: null, options: [], help: null }],
    tools: [],
    uses_user_data: true,
    uses_internet: true,
  },
]

const HEADLINE = 'Zakup zwiększy udział akcji'
const report = {
  headline: HEADLINE,
  facts: [{ label: 'Kwota zakupu', value: '1500.50', kind: 'money' }],
  tables: [],
  findings: [],
  recommendations: [],
  risks: [],
  sources: [],
  disclaimer: 'Informacja edukacyjna, nie porada.',
}
const result = {
  action: 'purchase_impact', run_id: 11, suggestion_id: 21, ai_status: 'ok', source: 'ai',
  report, model: 'm', provider: 'ollama', duration_ms: 90,
}
const stored = {
  id: 21, action: 'purchase_impact', source: 'ai', ai_status: 'ok', headline: HEADLINE, report,
  params: { amount: '1500.50' }, model: 'm', provider: 'ollama', run_id: 11,
  created_at: '2026-11-01T10:00:00Z', profile_used: false,
}

const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } })
const sse = (events: [string, unknown][]) =>
  new Response(
    new ReadableStream({
      start(c) {
        const enc = new TextEncoder()
        for (const [e, d] of events) c.enqueue(enc.encode(`event: ${e}\ndata: ${JSON.stringify(d)}\n\n`))
        c.close()
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
  )

let history: unknown[]
const runBodies: unknown[] = []
const suggestionFetches: string[] = []

beforeEach(() => {
  history = []
  runBodies.length = 0
  suggestionFetches.length = 0
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    if (url === '/api/agent/actions') return Promise.resolve(json(ACTIONS))
    if (url === '/api/agent/status') return Promise.resolve(json({ provider: 'ollama', model: 'm', available: true }))
    if (url.includes('/actions/') && url.endsWith('/run')) {
      runBodies.push({ url, body: JSON.parse(String(init?.body)), accept: (init?.headers as Record<string, string>)?.Accept })
      history = [stored]
      return Promise.resolve(
        sse([
          ['status', { message: 'Start' }],
          ['step', { index: 0, kind: 'tool', name: 'get_portfolio', status: 'ok', duration_ms: 5 }],
          ['result', result],
        ]),
      )
    }
    if (url.startsWith('/api/agent/suggestions')) {
      suggestionFetches.push(url)
      return Promise.resolve(json({ items: history, total: history.length }))
    }
    if (url.startsWith('/api/agent/runs')) return Promise.resolve(json({ items: [], total: 0 }))
    return Promise.resolve(json({}))
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/assistant']}>
        <AssistantPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Assistant full flow', () => {
  it('pick action -> params -> SSE -> report -> entry in history after reload', async () => {
    const first = mount()
    const group = await screen.findByRole('group', { name: 'Dostępne akcje' })
    await userEvent.click(within(group).getByRole('button', { name: /Wpływ zakupu/ }))
    await userEvent.type(await screen.findByLabelText(/Kwota/), '1500,50')
    await userEvent.click(screen.getByRole('button', { name: 'Uruchom' }))

    expect((await screen.findAllByText(HEADLINE)).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Informacja edukacyjna, nie porada.').length).toBeGreaterThan(0)

    expect(runBodies).toHaveLength(1)
    const sent = runBodies[0] as { url: string; body: { params: Record<string, unknown> }; accept: string }
    expect(sent.url).toBe('/api/agent/actions/purchase_impact/run')
    expect(sent.accept).toBe('text/event-stream')
    expect(sent.body.params).toMatchObject({ amount: '1500.50' })
    expect(typeof sent.body.params.amount).toBe('string') // money is a string, never a number

    // "refresh the page": fresh mount with a new query cache; history comes from the server
    first.unmount()
    suggestionFetches.length = 0
    mount()
    expect((await screen.findAllByText(HEADLINE)).length).toBeGreaterThan(0)
    expect(suggestionFetches.length).toBeGreaterThan(0)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('does not call the run endpoint before the user starts it', async () => {
    mount()
    await screen.findByRole('group', { name: 'Dostępne akcje' })
    expect(runBodies).toHaveLength(0)
  })
})
