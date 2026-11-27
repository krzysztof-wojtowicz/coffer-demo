import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Trend } from './queries'
import { SummaryTiles } from './SummaryTiles'

afterEach(cleanup)

const ch = (amount: string) => ({ amount, pct: null })
const trend = (over: Partial<Trend> = {}): Trend => ({
  month: '2026-11',
  months: [
    { month: '2026-10', income: '4000.00', expenses: '2000.00', balance: '2000.00', surplus: '2000.00', savings_rate: '50.0' },
    { month: '2026-11', income: '5000.00', expenses: '3000.00', balance: '-50.00', surplus: '2000.00', savings_rate: '40.0' },
  ],
  average: { income: '4000.00', expenses: '2000.00', balance: '2000.00', surplus: '2000.00', savings_rate: '50.0' },
  change: {
    income: ch('1000.00'),
    expenses: ch('1000.00'),
    balance: ch('-2050.00'),
    surplus: ch('0.00'),
    savings_rate: ch('-10.0'),
  },
  categories: [],
  ...over,
})

describe('SummaryTiles', () => {
  it('shows four tiles from the last month', () => {
    render(<SummaryTiles trend={trend()} />)
    for (const l of ['Przychody', 'Wydatki', 'Balans', 'Stopa oszczędności']) expect(screen.getByText(l)).toBeTruthy()
    expect(screen.getByTestId('tile-savings').textContent).toContain('40.0%'.replace('.', ','))
    expect(screen.getByTestId('tile-savings').parentElement!.textContent).toContain('−10,0 p.p. vs średnia')
    expect(screen.getByTestId('tile-balance').innerHTML).toContain('text-negative')
  })
  it('inverts colour for expenses change', () => {
    render(<SummaryTiles trend={trend()} />)
    const tile = screen.getByTestId('tile-expenses').parentElement!
    expect(tile.innerHTML).toContain('text-negative')
    expect(tile.textContent).toContain('vs średnia')
  })
  it('shows "brak danych" without an average', () => {
    render(<SummaryTiles trend={trend({ average: null, change: null })} />)
    expect(screen.getAllByText('brak danych')).toHaveLength(4)
  })
})
