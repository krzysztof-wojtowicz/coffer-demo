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
const advice = {
  top_picks: [
    { name: 'iShares MSCI World', asset_class: 'etf', symbol: 'IWDA.AS', rationale: 'Dywersyfikacja globalna', risk_level: 3, source_url: 'https://example.com/a' },
    { name: 'Obligacje skarbowe EDO', asset_class: 'bond', symbol: null, rationale: 'Ochrona przed inflacją', risk_level: 1, source_url: null },
    { name: 'Złoto', asset_class: 'commodity', symbol: 'GLD', rationale: 'Zabezpieczenie', risk_level: 2, source_url: null },
  ],
  tips: [{ title: 'Rebalansuj raz w roku', summary: 'Utrzymuj docelową alokację.', source: 'Bankier', url: 'https://example.com/t' }],
  llm_used: true,
  ai_status: 'ok',
  disclaimer: 'To nie jest porada inwestycyjna.',
}

let posts: Request[]
let adviceRequests: Request[]
let summaryBody: unknown
let adviceResponse: () => Response

beforeEach(() => {
  posts = []
  adviceRequests = []
  summaryBody = summary
  adviceResponse = () => json(advice)
  h.handler = (req) => {
    const path = new URL(req.url).pathname
    if (path === '/api/portfolio/summary') return json(summaryBody)
    if (path === '/api/portfolio/holdings' && req.method === 'POST') {
      posts.push(req)
      return json(holding, 201)
    }
    if (path === '/api/portfolio/holdings') return json([holding])
    if (path === '/api/agent/investment/advice') {
      adviceRequests.push(req)
      return adviceResponse()
    }
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
  it('pokazuje pozycje, podsumowanie i alokację', async () => {
    renderPage()
    expect(await screen.findByText('Apple')).toBeTruthy()
    expect(document.body.textContent).toContain('Wartość portfela')
    expect(document.body.textContent).toContain('+20,0%')
    expect(screen.getByRole('meter', { name: 'Akcje' }).getAttribute('aria-valuenow')).toBe('100')
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

  it('dodaje pozycję z poprawnym body', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await user.type(screen.getByLabelText('Nazwa'), 'Mieszkanie')
    await user.selectOptions(screen.getByLabelText('Klasa aktywów'), 'real_estate')
    await user.type(screen.getByLabelText('Ilość'), '1')
    await user.type(screen.getByLabelText('Cena zakupu (za jednostkę)'), '400000,50')
    await user.type(screen.getByLabelText(/Bieżąca wartość/), '500000')
    await user.click(screen.getByRole('button', { name: 'Dodaj' }))
    await waitFor(() => expect(posts.length).toBe(1))
    const body = await posts[0].json()
    expect(body).toMatchObject({
      name: 'Mieszkanie',
      asset_class: 'real_estate',
      quantity: '1',
      purchase_price: '400000.50',
      manual_value: '500000',
      currency: 'PLN',
      symbol: null,
    })
  })

  it('doradca AI pokazuje Top 3, porady i disclaimer', async () => {
    const user = renderPage()
    await screen.findByText('Apple')
    await user.click(screen.getByRole('button', { name: 'Pobierz rekomendacje' }))
    expect(await screen.findByText('Top 3 dla Ciebie teraz')).toBeTruthy()
    expect(screen.getByText('iShares MSCI World')).toBeTruthy()
    expect(screen.getByText('Rebalansuj raz w roku')).toBeTruthy()
    expect(screen.getByText('To nie jest porada inwestycyjna.')).toBeTruthy()
    const body = await adviceRequests[0].json()
    expect(body).toEqual({
      holdings: [{ symbol: 'AAPL', asset_class: 'stock', quantity: '10', current_value: '1200.00' }],
    })
  })

  it('doradca AI: pozycja bez przeliczenia na PLN ma current_value null', async () => {
    const chf = {
      ...summary.holdings[0],
      id: 2,
      name: 'Nestle',
      symbol: 'NESN.SW',
      currency: 'CHF',
      amount_currency: 'CHF',
      converted: false,
      current_value: '500.00',
      share_pct: null,
    }
    summaryBody = { ...summary, holdings: [...summary.holdings, chf], fx_missing: ['CHF'] }
    const user = renderPage()
    await screen.findByText('Nestle')
    await user.click(screen.getByRole('button', { name: 'Pobierz rekomendacje' }))
    await waitFor(() => expect(adviceRequests.length).toBe(1))
    const body = await adviceRequests[0].json()
    expect(body.holdings).toEqual([
      { symbol: 'AAPL', asset_class: 'stock', quantity: '10', current_value: '1200.00' },
      { symbol: 'NESN.SW', asset_class: 'stock', quantity: '10', current_value: null },
    ])
  })

  it.each([
    ['timeout', 'Model AI nie odpowiedział na czas'],
    ['limited', 'Osiągnięto dzienny limit zapytań do AI'],
    ['unavailable', 'Rekomendacje przygotowane bez modelu językowego (reguły).'],
  ])('doradca AI: ai_status %s daje polski komunikat i wynik regułowy', async (status, message) => {
    adviceResponse = () => json({ ...advice, llm_used: false, ai_status: status })
    const user = renderPage()
    await screen.findByText('Apple')
    await user.click(screen.getByRole('button', { name: 'Pobierz rekomendacje' }))
    const note = await screen.findByTestId('advisor-ai-status')
    expect(note.textContent).toContain(message)
    expect(screen.getByText('iShares MSCI World')).toBeTruthy()
  })

  it('doradca AI: brak endpointu daje polski komunikat', async () => {
    adviceResponse = () => json({ detail: 'Not Found' }, 404)
    const user = renderPage()
    await screen.findByText('Apple')
    await user.click(screen.getByRole('button', { name: 'Pobierz rekomendacje' }))
    expect(await screen.findByText('Doradca AI jest jeszcze niedostępny.')).toBeTruthy()
  })

  it('doradca AI: błąd serwera daje polski komunikat', async () => {
    adviceResponse = () => json({ detail: 'Usługa chwilowo niedostępna' }, 503)
    const user = renderPage()
    await screen.findByText('Apple')
    await user.click(screen.getByRole('button', { name: 'Pobierz rekomendacje' }))
    expect(await screen.findByText('Usługa chwilowo niedostępna')).toBeTruthy()
  })
})
