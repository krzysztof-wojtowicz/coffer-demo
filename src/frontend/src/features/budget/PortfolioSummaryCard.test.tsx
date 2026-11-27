import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PortfolioSummaryCard } from './PortfolioSummaryCard'

const h = vi.hoisted(() => ({ data: null as unknown }))
vi.mock('../portfolio/queries', async (orig) => ({
  ...(await orig<typeof import('../portfolio/queries')>()),
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

  it('shows target and gap next to the shares, or a link without a profile', () => {
    const data = {
      holdings: [holding],
      allocation: [{ asset_class: 'stock', value: '1200.00', share_pct: '100.0' }],
      total_value: '1200.00',
      total_cost: '1000.00',
      total_gain: '200.00',
      total_gain_pct: '20.0',
      prices_available: true,
      fx_missing: [],
    }
    h.data = {
      ...data,
      target: {
        classes: [
          { asset_class: 'stock', current_pct: '100.0', target_pct: '60', gap_pp: '40.0' },
          { asset_class: 'bond', current_pct: '0.0', target_pct: '40', gap_pp: '-40.0' },
        ],
        total_gap_pp: '40.0',
      },
    }
    const { unmount } = render(
      <MemoryRouter>
        <PortfolioSummaryCard />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Odchylenie od profilu: 40 pp/)).toBeTruthy()
    expect(screen.getByText('+40 pp')).toBeTruthy()
    expect(screen.getByText('-40 pp')).toBeTruthy()
    unmount()
    h.data = { ...data, target: null }
    render(
      <MemoryRouter>
        <PortfolioSummaryCard />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Ustaw profil inwestycyjny' }).getAttribute('href')).toBe('/account')
  })

  it('shows only the target when a profile exists but nothing is valued', () => {
    h.data = {
      holdings: [holding],
      allocation: [],
      total_value: '0',
      total_cost: '1000.00',
      total_gain: '0',
      total_gain_pct: null,
      prices_available: true,
      fx_missing: [],
      target: {
        classes: [{ asset_class: 'stock', current_pct: '0.0', target_pct: '11', gap_pp: null }],
        total_gap_pp: null,
      },
    }
    render(
      <MemoryRouter>
        <PortfolioSummaryCard />
      </MemoryRouter>,
    )
    expect(screen.getByText('cel 11%')).toBeTruthy()
    expect(screen.queryByText(/Odchylenie od profilu/)).toBeNull()
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
