import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { CategoryTrends } from './CategoryTrends'
import type { Trend } from './queries'
import { TrendChart } from './TrendChart'

afterEach(cleanup)

const months = ['2026-09', '2026-10', '2026-11'].map((m, i) => ({
  month: m,
  income: `${1000 * (i + 1)}.00`,
  expenses: `${500 * (i + 1)}.00`,
  balance: '0.00',
  surplus: '0.00',
  savings_rate: null,
}))
const cat = (i: number, change: string | null = '10.00') => ({
  category_id: i,
  category_name: `Kat ${i}`,
  amounts: ['0.00', '5.00', '15.00'],
  average: change === null ? null : '5.00',
  change,
  change_pct: change === null ? null : '200.0',
})
const trend = (n: number): Trend => ({
  month: '2026-11',
  months,
  average: null,
  change: null,
  categories: Array.from({ length: n }, (_, i) => cat(i + 1, i === 0 ? null : '10.00')),
})

describe('TrendChart', () => {
  it('labels months MM.YY and exposes a data table', () => {
    render(<TrendChart trend={trend(0)} />)
    expect(screen.getByText('09.26')).toBeTruthy()
    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getAllByRole('row')).toHaveLength(4)
    expect(screen.getByText('Miesiąc')).toBeTruthy()
  })
})

describe('CategoryTrends', () => {
  it('shows the empty text', () => {
    render(<CategoryTrends trend={trend(0)} />)
    expect(screen.getByText('Brak wydatków w tym miesiącu.')).toBeTruthy()
  })
  it('limits to 8 rows and expands, with "brak danych" for null change', async () => {
    render(<CategoryTrends trend={trend(10)} />)
    expect(screen.getAllByRole('row')).toHaveLength(9)
    expect(screen.getAllByText('brak danych').length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Pokaż wszystkie' }))
    expect(screen.getAllByRole('row')).toHaveLength(11)
  })
})
