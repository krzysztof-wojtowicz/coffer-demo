import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PortfolioSummaryCard } from './PortfolioSummaryCard'

const h = vi.hoisted(() => ({ data: null as unknown }))
vi.mock('../portfolio/queries', () => ({
  usePortfolioSummary: () => ({ data: h.data, error: null, isLoading: false }),
}))

const holding = {
  id: 1,
  name: 'Apple',
  symbol: 'AAPL',
  asset_class: 'stock',
  quantity: '10',
  currency: 'PLN',
  cost_basis: '1000.00',
  current_value: '1200.00',
  value_source: 'market',
  market_price: null,
  price_currency: null,
  amount_currency: 'PLN',
  converted: false,
  gain: '200.00',
  gain_pct: '20.0',
  share_pct: '100.0',
}

afterEach(cleanup)

describe('PortfolioSummaryCard', () => {
  it('shows value, invested, gain, allocation and top holdings', () => {
    h.data = {
      holdings: [holding],
      allocation: [{ asset_class: 'stock', value: '1200.00', share_pct: '100.0' }],
      total_value: '1200.00',
      total_cost: '1000.00',
      total_gain: '200.00',
      total_gain_pct: '20.0',
      prices_available: true,
      fx_missing: [],
    }
    render(
      <MemoryRouter>
        <PortfolioSummaryCard />
      </MemoryRouter>,
    )
    expect(screen.getByText('Zainwestowano')).toBeTruthy()
    expect(screen.getByText('Alokacja wg klas aktywów')).toBeTruthy()
    expect(screen.getByText('Apple')).toBeTruthy()
    expect(screen.getAllByText('+20,0%').length).toBe(2)
    expect(screen.getAllByText('100,0%').length).toBeGreaterThanOrEqual(2)
  })

  it('shows empty state', () => {
    h.data = { holdings: [], allocation: [], total_value: '0', total_cost: '0', total_gain: '0', total_gain_pct: null, prices_available: true, fx_missing: [] }
    render(
      <MemoryRouter>
        <PortfolioSummaryCard />
      </MemoryRouter>,
    )
    expect(screen.getByText('Dodaj pierwszą pozycję')).toBeTruthy()
  })
})
