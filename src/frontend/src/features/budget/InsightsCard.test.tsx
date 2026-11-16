import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { InsightsCard } from './InsightsCard'

const h = vi.hoisted(() => ({ body: null as unknown }))
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({
      baseUrl: 'http://localhost',
      fetch: () =>
        Promise.resolve(
          new Response(JSON.stringify(h.body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
        ),
    }),
  }
})

const base = {
  month: '2026-11',
  previous_month: '2026-10',
  comparison: [
    { category_id: 1, category_name: 'Jedzenie', current: '500.00', previous: '400.00', change: '100.00', change_pct: '25.0' },
    { category_id: 2, category_name: 'Transport', current: '50.00', previous: '0.00', change: '50.00', change_pct: null },
  ],
  top_growth: [
    { category_id: 1, category_name: 'Jedzenie', current: '500.00', average_3m: '400.00', increase: '100.00', increase_pct: '25.0' },
  ],
  limits: [
    { category_id: 1, category_name: 'Jedzenie', limit: '400.00', spent: '500.00', remaining: '-100.00', used_pct: '125.0', exceeded: true },
    { category_id: 3, category_name: 'Rozrywka', limit: '200.00', spent: '50.00', remaining: '150.00', used_pct: '25.0', exceeded: false },
  ],
}

function view() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <InsightsCard month="2026-11" />
    </QueryClientProvider>,
  )
}
beforeEach(() => {
  h.body = base
})
afterEach(cleanup)

describe('InsightsCard', () => {
  it('formats changes, null percent as dash and flags exceeded limits', async () => {
    view()
    expect(await screen.findByRole('table')).toBeTruthy()
    expect(screen.getByText('+25,0%')).toBeTruthy()
    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.getByText(/Przekroczono o/).textContent).toContain('100,00')
    const bars = screen.getAllByRole('progressbar')
    expect(bars[0].getAttribute('aria-valuenow')).toBe('125')
    expect(bars[1].getAttribute('aria-valuenow')).toBe('25')
    expect(screen.getByText(/ponad średnią z 3 mies\./)).toBeTruthy()
  })

  it('shows empty states', async () => {
    h.body = { ...base, comparison: [], top_growth: [], limits: [] }
    view()
    expect(await screen.findByText('Brak wydatków do porównania.')).toBeTruthy()
    expect(screen.getByText(/Brak kategorii z wydatkami powyżej średniej/)).toBeTruthy()
    expect(screen.getByText('Nie ustawiono żadnych limitów.')).toBeTruthy()
  })
})
