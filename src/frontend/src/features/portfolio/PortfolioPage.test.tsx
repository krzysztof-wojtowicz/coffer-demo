import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PortfolioPage } from './PortfolioPage'

const h = vi.hoisted(() => ({
  handler: null as null | ((req: Request) => Response | Promise<Response>),
}))
const fakeFetch = (input: RequestInfo | URL, init?: RequestInit) => {
  const req =
    input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
  return Promise.resolve(h.handler!(req))
}
vi.stubGlobal('fetch', fakeFetch)
// openapi-fetch needs an absolute base URL outside the browser.
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({ baseUrl: 'http://localhost', fetch: (r: Request) => globalThis.fetch(r) }),
  }
})
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const holding = {
  id: 1,
  name: 'Apple',
  symbol: 'AAPL',
  asset_class: 'stock',
  quantity: '10',
  purchase_price: '100.00',
  currency: 'PLN',
  purchase_date: null,
  manual_value: null,
  note: null,
  created_at: '2026-11-05T10:00:00Z',
}
const summary = {
  holdings: [
    {
      id: 1,
      name: 'Apple',
      symbol: 'AAPL',
      asset_class: 'stock',
      quantity: '10',
      currency: 'PLN',
      cost_basis: '1000.00',
      current_value: '1200.00',
      value_source: 'market',
      market_price: '30.00',
      price_currency: 'USD',
      amount_currency: 'PLN',
      converted: true,
      gain: '200.00',
      gain_pct: '20.0',
      share_pct: '100.0',
    },
  ],
  allocation: [{ asset_class: 'stock', value: '1200.00', share_pct: '100.0' }],
  total_value: '1200.00',
  total_cost: '1000.00',
  total_gain: '200.00',
  total_gain_pct: '20.0',
  prices_available: true,
  fx_missing: [] as string[],
}

let posts: Request[]
let summaryBody: unknown

beforeEach(() => {
  posts = []
  summaryBody = summary
  h.handler = (req) => {
    const path = new URL(req.url).pathname
    if (path === '/api/portfolio/summary') return json(summaryBody)
    if (path === '/api/portfolio/holdings' && req.method === 'POST') {
      posts.push(req)
      return json(holding, 201)
    }
    if (path === '/api/portfolio/holdings') return json([holding])
    return json({ detail: 'Not Found' }, 404)
  }
})
afterEach(cleanup)

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PortfolioPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return user
}

describe('PortfolioPage', () => {
  it('pokazuje datę cen', async () => {
    summaryBody = {
      ...summary,
      prices_as_of: '2026-11-10T08:30:00Z',
      holdings: [{ ...summary.holdings[0], as_of: '2020-01-01T00:00:00Z' }],
    }
    renderPage()
    expect(await screen.findByText(/Ceny z: /)).toBeTruthy()
    expect(screen.getByText(/cena z 01\.01\.2020/)).toBeTruthy()
  })

  it('formularz jest ukryty, przycisk go pokazuje, Edytuj wypełnia go', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    expect(screen.queryByLabelText(/Klasa aktywów/)).toBeNull()
    // Order: chart, table, then the add button.
    const chart = screen.getByRole('img')
    const table = screen.getByRole('table')
    const add = screen.getByRole('button', { name: 'Dodaj pozycję' })
    expect(chart.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(table.compareDocumentPosition(add) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await user.click(add)
    expect(screen.getByLabelText(/Klasa aktywów/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(screen.queryByLabelText(/Klasa aktywów/)).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Edytuj' }))
    expect((screen.getByLabelText(/^Nazwa/) as HTMLInputElement).value).toBe('Apple')
    expect(screen.getByRole('button', { name: 'Zapisz zmiany' })).toBeTruthy()
  })

  it('pokazuje cel i odchylenie obok udziałów', async () => {
    summaryBody = {
      ...summary,
      allocation: [
        { asset_class: 'stock', value: '700.00', share_pct: '70.0' },
        { asset_class: 'bond', value: '300.00', share_pct: '30.0' },
      ],
      target: {
        classes: [
          { asset_class: 'stock', current_pct: '70.0', target_pct: '34', gap_pp: '36.0' },
          { asset_class: 'bond', current_pct: '30.0', target_pct: '40', gap_pp: '-10.0' },
          { asset_class: 'etf', current_pct: '0.0', target_pct: '26', gap_pp: '-26.0' },
        ],
        total_gap_pp: '36.0',
      },
    }
    renderPage()
    expect(await screen.findByText(/Odchylenie od profilu: 36 pp/)).toBeTruthy()
    const row = screen.getAllByText('Akcje').map((e) => e.closest('li')).find(Boolean)
    expect(row?.textContent).toContain('cel 34%')
    expect(row?.textContent).toContain('+36 pp')
    expect(screen.getByText('ETF').closest('li')?.textContent).toContain('-26 pp')
  })

  it('pusty portfel z profilem pokazuje sam cel bez porównania', async () => {
    summaryBody = {
      ...summary,
      allocation: [],
      target: {
        classes: [{ asset_class: 'stock', current_pct: '0.0', target_pct: '11', gap_pp: null }],
        total_gap_pp: null,
      },
    }
    renderPage()
    const row = (await screen.findAllByText('Akcje')).map((e) => e.closest('li')).find(Boolean)
    expect(row?.textContent).toContain('cel 11%')
    expect(row?.textContent).not.toMatch(/pp/)
    expect(document.body.textContent).not.toContain('Odchylenie od profilu')
  })

  it('bez profilu linkuje do konta', async () => {
    summaryBody = { ...summary, target: null }
    renderPage()
    const link = await screen.findByRole('link', { name: 'Ustaw profil inwestycyjny' })
    expect(link.getAttribute('href')).toBe('/account')
  })

  it('pokazuje pozycje, podsumowanie i alokację', async () => {
    renderPage()
    expect(await screen.findByText('Apple')).toBeTruthy()
    expect(document.body.textContent).toContain('Wartość portfela')
    expect(document.body.textContent).toContain('+20,0%')
    const chart = screen.getByRole('img', { name: /Akcje 100,0%/ })
    expect(chart.getAttribute('aria-label')).toContain('Akcje 100,0%')
    const legendRow = screen.getAllByText('Akcje').map((e) => e.closest('li')).find(Boolean)
    expect(legendRow?.textContent).toContain('100,0%')
    expect(document.body.textContent).not.toContain('Notowania rynkowe są chwilowo niedostępne')
  })

  it('informuje o braku notowań', async () => {
    summaryBody = { ...summary, prices_available: false }
    renderPage()
    expect(await screen.findByText(/Notowania rynkowe są chwilowo niedostępne/)).toBeTruthy()
  })

  it('ostrzega o brakującym kursie walut', async () => {
    summaryBody = { ...summary, fx_missing: ['CHF'] }
    renderPage()
    expect(await screen.findByText(/Brak kursu walut: CHF/)).toBeTruthy()
  })

  async function openForm(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole('button', { name: 'Dodaj pozycję' }))
  }

  async function pickClass(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
    await user.click(screen.getByLabelText(/Klasa aktywów/))
    await user.click(screen.getByRole('option', { name }))
  }

  it('na starcie pokazuje tylko klasę i nazwę', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await openForm(user)
    expect(screen.getByLabelText(/Klasa aktywów/)).toBeTruthy()
    expect(screen.getByLabelText(/^Nazwa/)).toBeTruthy()
    for (const l of [/Symbol/, /Waluta/, /Ilość/, /Cena/, /Data zakupu/, /Bieżąca wartość/, /Notatka/]) {
      expect(screen.queryByLabelText(l)).toBeNull()
    }
    expect(document.body.textContent).not.toContain('Dla aktywów bez notowań')
  })

  it('pokazuje pola zależnie od klasy i czyści nieużywane przy zmianie', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await openForm(user)
    await pickClass(user, /^Akcje/)
    expect(screen.getByLabelText(/Symbol \(ticker\)/)).toBeTruthy()
    expect(screen.getByLabelText(/^Ilość/)).toBeTruthy()
    expect(screen.queryByLabelText(/Bieżąca wartość/)).toBeNull()
    await user.type(screen.getByLabelText(/Symbol \(ticker\)/), 'aapl')
    await pickClass(user, /Nieruchomości/)
    expect(screen.queryByLabelText(/Symbol/)).toBeNull()
    expect(screen.queryByLabelText(/^Ilość/)).toBeNull()
    expect(screen.getByLabelText(/Bieżąca wartość/)).toBeTruthy()
    await pickClass(user, /^Akcje/)
    expect((screen.getByLabelText(/Symbol \(ticker\)/) as HTMLInputElement).value).toBe('')
  })

  it('dodaje akcję z poprawnym body', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await openForm(user)
    await pickClass(user, /^Akcje/)
    await user.type(screen.getByLabelText(/^Nazwa/), 'Apple')
    await user.type(screen.getByLabelText(/Symbol \(ticker\)/), 'aapl')
    await user.clear(screen.getByLabelText(/^Waluta/))
    await user.type(screen.getByLabelText(/^Waluta/), 'usd')
    await user.type(screen.getByLabelText(/^Ilość/), '10')
    await user.type(screen.getByLabelText(/^Cena za jednostkę/), '150,5')
    await user.click(screen.getByRole('button', { name: 'Dodaj' }))
    await waitFor(() => expect(posts.length).toBe(1))
    expect(await posts[0].json()).toEqual({
      name: 'Apple',
      asset_class: 'stock',
      symbol: 'AAPL',
      quantity: '10',
      purchase_price: '150.5',
      currency: 'USD',
      purchase_date: null,
      manual_value: null,
      note: null,
    })
  })

  it('dodaje nieruchomość z ilością 1 i bez symbolu', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await openForm(user)
    await pickClass(user, /Nieruchomości/)
    await user.type(screen.getByLabelText(/^Nazwa/), 'Mieszkanie')
    await user.type(screen.getByLabelText(/^Cena zakupu/), '400000,50')
    await user.type(screen.getByLabelText(/Bieżąca wartość/), '500000')
    await user.click(screen.getByRole('button', { name: 'Dodaj' }))
    await waitFor(() => expect(posts.length).toBe(1))
    expect(await posts[0].json()).toEqual({
      name: 'Mieszkanie',
      asset_class: 'real_estate',
      symbol: null,
      quantity: '1',
      purchase_price: '400000.50',
      currency: 'PLN',
      purchase_date: null,
      manual_value: '500000',
      note: null,
    })
  })
})
