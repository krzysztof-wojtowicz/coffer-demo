import { describe, expect, it } from 'vitest'
import { categoryTagClass, compareAmounts, defaultOptions, filterAndSort, uniqueSources } from './list'

const mk = (id: number, date: string, amount: string, category_id = 1, source = 'manual') => ({
  id,
  date,
  amount,
  category_id,
  source,
})
const data = [
  mk(1, '2026-01-05', '-10.00'),
  mk(2, '2026-01-20', '1500.00', 2, 'import'),
  mk(3, '2026-01-10', '-99.50', 2, 'import'),
]

describe('filterAndSort', () => {
  it('sorts by date desc by default', () => {
    expect(filterAndSort(data, defaultOptions).map((t) => t.id)).toEqual([2, 3, 1])
  })
  it('sorts by amount asc', () => {
    const r = filterAndSort(data, { ...defaultOptions, sortKey: 'amount', sortDir: 'asc' })
    expect(r.map((t) => t.id)).toEqual([3, 1, 2])
  })
  it('filters by type', () => {
    expect(filterAndSort(data, { ...defaultOptions, type: 'income' }).map((t) => t.id)).toEqual([2])
    expect(filterAndSort(data, { ...defaultOptions, type: 'expense' })).toHaveLength(2)
  })
  it('filters by category and source', () => {
    const r = filterAndSort(data, { ...defaultOptions, categoryId: 2, source: 'import' })
    expect(r.map((t) => t.id)).toEqual([2, 3])
    expect(filterAndSort(data, { ...defaultOptions, categoryId: 1 })).toHaveLength(1)
  })
  it('does not mutate input', () => {
    const copy = [...data]
    filterAndSort(data, defaultOptions)
    expect(data).toEqual(copy)
  })
})

describe('helpers', () => {
  it('compares decimals exactly', () => {
    expect(compareAmounts('-0.10', '-0.2')).toBe(1)
    expect(compareAmounts('10', '10.00')).toBe(0)
  })
  it('lists unique sources', () => {
    expect(uniqueSources(data)).toEqual(['import', 'manual'])
  })
  it('tag class is deterministic', () => {
    expect(categoryTagClass(3)).toBe(categoryTagClass(3))
  })
})
