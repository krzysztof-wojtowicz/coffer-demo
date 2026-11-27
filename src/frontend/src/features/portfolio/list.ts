import { compareAmounts } from '../../lib/decimal'
import type { components } from '../../api/schema'

export type Position = components['schemas']['PositionOut']
export type PositionSortKey = 'value' | 'name' | 'gain' | 'gain_pct' | 'date'
export type PositionSortDir = 'asc' | 'desc'

export interface PositionListOptions {
  assetClass: string | null
  query: string
  sortKey: PositionSortKey
  sortDir: PositionSortDir
}

export const defaultPositionOptions: PositionListOptions = {
  assetClass: null,
  query: '',
  sortKey: 'value',
  sortDir: 'desc',
}

type PositionLike = Pick<Position, 'key' | 'name' | 'symbol' | 'asset_class' | 'value' | 'gain' | 'gain_pct' | 'latest_purchase_date'>

function sortValue(p: PositionLike, k: PositionSortKey): string | null {
  switch (k) {
    case 'value':
      return p.value
    case 'name':
      return p.name
    case 'gain':
      return p.gain
    case 'gain_pct':
      return p.gain_pct
    case 'date':
      return p.latest_purchase_date
  }
}

export function filterAndSortPositions<T extends PositionLike>(items: T[], o: PositionListOptions): T[] {
  const q = o.query.trim().toLowerCase()
  const out = items.filter(
    (p) =>
      (o.assetClass === null || p.asset_class === o.assetClass) &&
      (q === '' || p.name.toLowerCase().includes(q) || (p.symbol ?? '').toLowerCase().includes(q)),
  )
  const sign = o.sortDir === 'asc' ? 1 : -1
  return out.sort((a, b) => {
    const x = sortValue(a, o.sortKey)
    const y = sortValue(b, o.sortKey)
    // Nulls go last whichever the direction, so they are decided before the sign applies.
    if (x === null || y === null) {
      if (x !== y) return x === null ? 1 : -1
    } else {
      const c =
        o.sortKey === 'name'
          ? x.localeCompare(y, 'pl')
          : o.sortKey === 'date'
            ? x < y
              ? -1
              : x > y
                ? 1
                : 0
            : compareAmounts(x, y)
      if (c !== 0) return c * sign
    }
    return a.key < b.key ? -1 : a.key > b.key ? 1 : 0
  })
}
