import { describe, expect, it } from 'vitest'
import { defaultPositionOptions, filterAndSortPositions } from './list'

const mk = (
  key: string,
  name: string,
  symbol: string | null,
  asset_class: string,
  value: string | null,
  gain: string | null,
  gain_pct: string | null,
  latest_purchase_date: string | null = null,
) => ({ key, name, symbol, asset_class, value, gain, gain_pct, latest_purchase_date })

const data = [
  mk('AAPL', 'Apple Inc.', 'AAPL', 'stock', '6000.00', '1000.00', '20.0', '2024-09-02'),
  mk('VWCE.DE', 'Vanguard FTSE All-World', 'VWCE.DE', 'etf', '3000.00', '-100.00', '-3.2', '2025-01-10'),
  mk('id:7', 'Mieszkanie', null, 'real_estate', '500000.00', '100000.00', '25.0', null),
  mk('CHF', 'Szwajcaria', 'CHF', 'stock', null, null, null, '2023-05-01'),
]
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = (o: Record<string, unknown>) =>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  filterAndSortPositions(data as any, { ...defaultPositionOptions, ...o } as any).map((p: any) => p.key)

describe('filterAndSortPositions', () => {
  it('defaults to value descending, null value last', () => {
    expect(run({})).toEqual(['id:7', 'AAPL', 'VWCE.DE', 'CHF'])
  })
  it('filters by asset class', () => {
    expect(run({ assetClass: 'etf' })).toEqual(['VWCE.DE'])
    expect(run({ assetClass: 'stock' })).toEqual(['AAPL', 'CHF'])
  })
  it('searches name or ticker case-insensitively', () => {
    expect(run({ query: 'vwce' })).toEqual(['VWCE.DE'])
    expect(run({ query: 'apple' })).toEqual(['AAPL'])
    expect(run({ query: 'MIESZK' })).toEqual(['id:7'])
  })
  it('search matching nothing returns an empty list', () => {
    expect(run({ query: 'zzz' })).toEqual([])
  })
  it('sorts by gain % descending with null last', () => {
    expect(run({ sortKey: 'gain_pct', sortDir: 'desc' })).toEqual(['id:7', 'AAPL', 'VWCE.DE', 'CHF'])
  })
  it('sorts by gain % ascending with null still last', () => {
    expect(run({ sortKey: 'gain_pct', sortDir: 'asc' })).toEqual(['VWCE.DE', 'AAPL', 'id:7', 'CHF'])
  })
  it('sorts by gain amount with null last in both directions', () => {
    expect(run({ sortKey: 'gain', sortDir: 'desc' })).toEqual(['id:7', 'AAPL', 'VWCE.DE', 'CHF'])
    expect(run({ sortKey: 'gain', sortDir: 'asc' })).toEqual(['VWCE.DE', 'AAPL', 'id:7', 'CHF'])
  })
  it('sorts by value ascending with null last', () => {
    expect(run({ sortKey: 'value', sortDir: 'asc' })).toEqual(['VWCE.DE', 'AAPL', 'id:7', 'CHF'])
  })
  it('sorts by name', () => {
    expect(run({ sortKey: 'name', sortDir: 'asc' })).toEqual(['AAPL', 'id:7', 'CHF', 'VWCE.DE'])
  })
  it('sorts by latest purchase date with null last in both directions', () => {
    expect(run({ sortKey: 'date', sortDir: 'desc' })).toEqual(['VWCE.DE', 'AAPL', 'CHF', 'id:7'])
    expect(run({ sortKey: 'date', sortDir: 'asc' })).toEqual(['CHF', 'AAPL', 'VWCE.DE', 'id:7'])
  })
  it('compares large decimal strings exactly', () => {
    const big = [mk('a', 'A', 'A', 'cash', '10000000000.01', '0', '0'), mk('b', 'B', 'B', 'cash', '10000000000.02', '0', '0')]
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(filterAndSortPositions(big as any, defaultPositionOptions as any).map((p: any) => p.key)).toEqual(['b', 'a'])
  })
})
