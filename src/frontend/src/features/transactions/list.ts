export type TypeFilter = 'all' | 'income' | 'expense'
export type SortKey = 'date' | 'amount'
export type SortDir = 'asc' | 'desc'

export interface TxLike {
  id: number
  date: string
  amount: string
  category_id: number
  source: string
}

export interface ListOptions {
  type: TypeFilter
  categoryId: number | null
  source: string | null
  sortKey: SortKey
  sortDir: SortDir
}

export const defaultOptions: ListOptions = {
  type: 'all',
  categoryId: null,
  source: null,
  sortKey: 'date',
  sortDir: 'desc',
}

/** Compare two decimal strings without floats (sign, then integer and fraction digits). */
export function compareAmounts(a: string, b: string): number {
  const norm = (v: string) => {
    const neg = v.trim().startsWith('-')
    const [i = '0', f = ''] = v.trim().replace(/^[-+]/, '').split('.')
    const digits = BigInt(i + f.padEnd(6, '0').slice(0, 6))
    return neg ? -digits : digits
  }
  const x = norm(a)
  const y = norm(b)
  return x < y ? -1 : x > y ? 1 : 0
}

export function filterAndSort<T extends TxLike>(items: T[], o: ListOptions): T[] {
  const out = items.filter((t) => {
    if (o.type === 'income' && compareAmounts(t.amount, '0') < 0) return false
    if (o.type === 'expense' && compareAmounts(t.amount, '0') >= 0) return false
    if (o.categoryId !== null && t.category_id !== o.categoryId) return false
    if (o.source !== null && t.source !== o.source) return false
    return true
  })
  const sign = o.sortDir === 'asc' ? 1 : -1
  return out.sort((a, b) => {
    const c =
      o.sortKey === 'date'
        ? a.date < b.date
          ? -1
          : a.date > b.date
            ? 1
            : 0
        : compareAmounts(a.amount, b.amount)
    return c !== 0 ? c * sign : (a.id - b.id) * sign
  })
}

export function uniqueSources(items: { source: string }[]): string[] {
  return [...new Set(items.map((t) => t.source))].sort()
}

const palette = [
  'bg-info/10 text-info',
  'bg-positive/10 text-positive',
  'bg-warning/10 text-warning',
  'bg-negative/10 text-negative',
  'bg-accent-soft text-accent',
  'bg-surface-2 text-text',
]

/** Deterministic tag classes for a category id. */
export function categoryTagClass(categoryId: number): string {
  return palette[Math.abs(Math.trunc(categoryId)) % palette.length]
}
