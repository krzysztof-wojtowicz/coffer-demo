import { pl } from '../../i18n/pl'

const L = pl.assistant

export const actionLabel = (id: string): string => L.actionNames[id] ?? L.kind[id] ?? id
export const toolLabel = (name: string): string => L.toolNames[name] ?? name
export const providerLabel = (p: string | null | undefined): string =>
  p ? (L.providers[p] ?? p) : '—'
export const runStatusLabel = (s: string): string => L.runStatus[s] ?? s
export const isLegacyAction = (id: string): boolean => id === 'surplus' || id === 'advisor'

/** Display label of an action, with the "archival" prefix for legacy ones. */
export function actionDisplay(id: string): string {
  return isLegacyAction(id) ? `${L.archivalPrefix}: ${actionLabel(id)}` : actionLabel(id)
}

export function runTone(status: string): 'success' | 'danger' | 'warning' | 'neutral' {
  if (status === 'ok') return 'success'
  if (status === 'invalid' || status === 'error') return 'danger'
  if (status === 'unavailable' || status === 'limited' || status === 'timeout') return 'warning'
  return 'neutral'
}

export function formatCost(cost: string | null | undefined): string {
  if (cost == null) return '—'
  const n = Number(cost)
  if (Number.isNaN(n)) return '—'
  if (n === 0) return '$0'
  return `~$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}`
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(Math.round(ms / 100) / 10).toFixed(1).replace('.', ',')} s`
}

export function formatTokens(i: number | null | undefined, o: number | null | undefined): string {
  if (i == null && o == null) return '—'
  return `${i ?? '—'} / ${o ?? '—'}`
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('pl-PL')
}

/** Format a fact value by its kind (pl-PL separators). */
export function formatValue(value: string, kind: string): string {
  const n = Number(value)
  if (kind === 'money') {
    return Number.isNaN(n)
      ? value
      : new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(n)
  }
  if (kind === 'percent') {
    return Number.isNaN(n)
      ? value
      : `${new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 2 }).format(n)}%`
  }
  if (kind === 'number') {
    return Number.isNaN(n)
      ? value
      : new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 4 }).format(n)
  }
  if (kind === 'date') {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString('pl-PL')
  }
  return value
}

/** Polish label of a select option (asset classes come from the portfolio dictionary). */
export function optionLabel(param: string, value: string): string {
  if (param === 'asset_class') return pl.portfolio.classes[value] ?? value
  return value
}

/** Formats a finding value: plain decimals as money, everything else as given. */
export function formatFindingValue(value: string): string {
  return /^-?\d+\.\d{2}$/.test(value) ? formatValue(value, 'money') : value
}
