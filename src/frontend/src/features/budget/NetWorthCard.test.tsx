import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { NetWorthCard } from './NetWorthCard'

const h = vi.hoisted(() => ({ data: null as unknown }))
vi.mock('./queries', () => ({
  useNetWorth: () => ({ data: h.data, error: null, isLoading: false }),
}))

const base = {
  cash_balance: '1000.00',
  portfolio_value: '2000.00',
  net_worth: '3000.00',
  portfolio_complete: true,
  as_of: '2026-11-12',
  opening_balance_set: true,
}

afterEach(cleanup)

describe('NetWorthCard', () => {
  it('shows three values and as-of date', () => {
    h.data = base
    render(<NetWorthCard />, { wrapper: MemoryRouter })
    expect(screen.getByText('Środki na kontach')).toBeTruthy()
    expect(screen.getByText('Portfel inwestycyjny')).toBeTruthy()
    expect(screen.getByText('Wartość netto')).toBeTruthy()
    expect(screen.getByTestId('net-worth-total').textContent).toContain('3')
    expect(screen.getByText(/stan na 2026-11-12/)).toBeTruthy()
    expect(screen.queryByText(/nie została wyceniona/)).toBeNull()
  })
  it('warns when portfolio is incomplete', () => {
    h.data = { ...base, portfolio_complete: false }
    render(<NetWorthCard />, { wrapper: MemoryRouter })
    expect(screen.getByText(/nie została wyceniona/)).toBeTruthy()
  })
  it('hints at setting the balance (link to /account) only when it is not set', () => {
    h.data = { ...base, opening_balance_set: false }
    const { unmount } = render(<NetWorthCard />, { wrapper: MemoryRouter })
    expect(screen.getByText(/Ustaw saldo konta, aby środki odpowiadały stanowi w banku/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ustaw saldo' }).getAttribute('href')).toBe('/account')
    unmount()
    h.data = base
    render(<NetWorthCard />, { wrapper: MemoryRouter })
    expect(screen.queryByText(/Ustaw saldo konta/)).toBeNull()
  })
})
