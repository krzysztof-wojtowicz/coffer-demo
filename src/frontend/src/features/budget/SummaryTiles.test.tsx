import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SummaryTiles } from './SummaryTiles'

const h = vi.hoisted(() => ({ balance: '0.00' }))
vi.mock('./queries', () => ({
  useBudget: () => ({
    data: {
      income: '5000.00',
      expenses: '3000.00',
      balance: h.balance,
      surplus: '9999.00',
      by_category: [],
    },
    error: null,
    isLoading: false,
  }),
}))

afterEach(cleanup)

describe('SummaryTiles', () => {
  it('shows only income, expenses and balance (no Saldo)', () => {
    render(<SummaryTiles month="2026-11" />)
    expect(screen.getByText('Przychody')).toBeTruthy()
    expect(screen.getByText('Wydatki')).toBeTruthy()
    expect(screen.getByText('Balans')).toBeTruthy()
    expect(screen.queryByText('Saldo')).toBeNull()
    expect(screen.queryByText('Nadwyżka')).toBeNull()
  })
  it.each([
    ['1200.00', 'text-positive'],
    ['-50.00', 'text-negative'],
  ])('colors balance %s as %s', (balance, cls) => {
    h.balance = balance
    render(<SummaryTiles month="2026-11" />)
    expect(screen.getByTestId('tile-balance').innerHTML).toContain(cls)
  })
  it('keeps zero balance neutral', () => {
    h.balance = '0.00'
    render(<SummaryTiles month="2026-11" />)
    const html = screen.getByTestId('tile-balance').innerHTML
    expect(html).not.toContain('text-positive')
    expect(html).not.toContain('text-negative')
  })
})
