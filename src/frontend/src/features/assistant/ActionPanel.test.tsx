import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ActionPanel } from './ActionPanel'

const ACTIONS = [
  {
    id: 'portfolio_review',
    name: 'Analiza portfela',
    description: 'Przegląd portfela',
    params: [],
    tools: [],
    uses_user_data: true,
    uses_internet: false,
  },
  {
    id: 'purchase_impact',
    name: 'Wpływ zakupu na portfel',
    description: 'Co zmieni zakup',
    params: [
      { name: 'amount', label: 'Kwota', kind: 'amount', required: true, default: null, options: [], help: null },
      { name: 'asset_class', label: 'Klasa', kind: 'select', required: false, default: 'etf', options: ['etf', 'stock'], help: null },
      { name: 'symbol', label: 'Symbol', kind: 'symbol', required: false, default: null, options: [], help: null },
    ],
    tools: [],
    uses_user_data: true,
    uses_internet: true,
  },
]

const report = {
  headline: 'Portfel jest zdywersyfikowany',
  facts: [{ label: 'Wartość', value: '1200.50', kind: 'money' }],
  tables: [],
  findings: [],
  recommendations: [],
  risks: [],
  sources: [],
  disclaimer: 'To jest sugestia informacyjna.',
}
const resultBody = {
  action: 'portfolio_review', run_id: 7, suggestion_id: 3, ai_status: 'ok', source: 'ai',
  report, model: 'm', provider: 'ollama', duration_ms: 100,
}

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
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } })

let runResponse: (init: RequestInit) => Response
const calls: { url: string; init?: RequestInit }[] = []

beforeEach(() => {
  calls.length = 0
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url === '/api/agent/actions') return Promise.resolve(json(ACTIONS))
    if (url === '/api/agent/status') return Promise.resolve(json({ provider: 'ollama', model: 'm', available: true }))
    if (url.includes('/run')) return Promise.resolve(runResponse(init ?? {}))
    return Promise.resolve(json({}))
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function setup(path = '/assistant') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <ActionPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
const runCalls = () => calls.filter((c) => c.url.includes('/run'))

describe('ActionPanel', () => {
  it('builds the form from ParamSpec and validates the amount', async () => {
    setup('/assistant?action=purchase_impact')
    const amount = await screen.findByLabelText(/Kwota/)
    expect(screen.getByLabelText('Symbol')).toBeTruthy()
    await userEvent.type(amount, 'abc')
    await userEvent.click(screen.getByRole('button', { name: 'Uruchom' }))
    expect(await screen.findByText(/maksymalnie 2 miejscami/)).toBeTruthy()
    expect(runCalls()).toHaveLength(0)
  })

  it('sends a comma amount as a dot string and prefills from the URL', async () => {
    runResponse = () => sse([['result', resultBody]])
    setup('/assistant?action=purchase_impact&symbol=VWCE.DE')
    expect(((await screen.findByLabelText('Symbol')) as HTMLInputElement).value).toBe('VWCE.DE')
    await userEvent.type(screen.getByLabelText(/Kwota/), '1500,50')
    await userEvent.click(screen.getByRole('button', { name: 'Uruchom' }))
    await screen.findByText(report.headline)
    const body = JSON.parse(String(runCalls()[0].init?.body))
    expect(body.params).toMatchObject({ amount: '1500.50', symbol: 'VWCE.DE', asset_class: 'etf' })
  })

  it('shows step events live and the report on result', async () => {
    runResponse = () =>
      sse([
        ['status', { message: 'Liczę' }],
        ['step', { index: 0, kind: 'tool', name: 'get_portfolio', status: 'ok', duration_ms: 12 }],
        ['result', resultBody],
      ])
    setup('/assistant?action=portfolio_review')
    await userEvent.click(await screen.findByRole('button', { name: 'Uruchom' }))
    expect(await screen.findByText(report.headline)).toBeTruthy()
    expect(screen.getByText('To jest sugestia informacyjna.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Pokaż ślad' }).getAttribute('href')).toBe('/assistant/runs/7')
  })

  it('shows an SSE error event as a message', async () => {
    runResponse = () => sse([['error', { detail: 'Coś poszło nie tak' }]])
    setup('/assistant?action=portfolio_review')
    await userEvent.click(await screen.findByRole('button', { name: 'Uruchom' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Coś poszło nie tak')
  })

  it('cancel aborts the request', async () => {
    let signal: AbortSignal | undefined
    runResponse = (init) => {
      signal = init.signal ?? undefined
      return new Response(
        new ReadableStream({
          start(c) {
            signal?.addEventListener('abort', () => c.error(new DOMException('aborted', 'AbortError')))
          },
        }),
        { status: 200 },
      )
    }
    setup('/assistant?action=portfolio_review')
    await userEvent.click(await screen.findByRole('button', { name: 'Uruchom' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Anuluj' }))
    await waitFor(() => expect(signal?.aborted).toBe(true))
    expect(await screen.findByText('Przerwano.')).toBeTruthy()
  })
})

describe('ActionPanel 422 mapping', () => {
  it('shows validator messages next to the field', async () => {
    runResponse = () =>
      new Response(
        JSON.stringify({
          detail: [{ loc: ['body', 'params', 'amount'], msg: 'Value error, Podaj dokładnie jedno: kwotę albo liczbę sztuk', type: 'value_error' }],
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      )
    setup('/assistant?action=purchase_impact')
    await userEvent.type(await screen.findByLabelText(/Kwota/), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Uruchom' }))
    expect(await screen.findByText('Podaj dokładnie jedno: kwotę albo liczbę sztuk')).toBeTruthy()
  })

  it('rejects more than 2 decimals in amounts and leaves optional month unsent', async () => {
    setup('/assistant?action=purchase_impact')
    await userEvent.type(await screen.findByLabelText(/Kwota/), '1,234')
    await userEvent.click(screen.getByRole('button', { name: 'Uruchom' }))
    expect(await screen.findByText(/maksymalnie 2 miejscami/)).toBeTruthy()
    expect(runCalls()).toHaveLength(0)
  })
})
