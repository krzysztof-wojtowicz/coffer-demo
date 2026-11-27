// API amounts and percentages are decimal strings. They are only formatted
// here, never summed or derived (see CLAUDE.md money rules).

const formatters = new Map<string, Intl.NumberFormat | null>()

function formatterFor(currency: string): Intl.NumberFormat | null {
  if (!formatters.has(currency)) {
    let f: Intl.NumberFormat | null = null
    try {
      f = new Intl.NumberFormat('pl-PL', { style: 'currency', currency })
    } catch {
      // Intl rejects malformed currency codes; the caller falls back to plain text.
    }
    formatters.set(currency, f)
  }
  return formatters.get(currency) ?? null
}

export function formatMoney(value: string, currency = 'PLN'): string {
  const f = formatterFor(currency)
  return f ? f.format(Number(value)) : `${value} ${currency}`
}

/** Sign of a decimal string. Number() is used only to compare with zero, never for display. */
export function signOf(value: string): -1 | 0 | 1 {
  const n = Number(value)
  // "-0.00" parses to -0 and must count as zero, so it gets neither colour nor "+".
  return n > 0 ? 1 : n < 0 ? -1 : 0
}

export function formatPct(value: string | null, opts: { signed?: boolean } = {}): string {
  if (value === null) return '–'
  const plus = opts.signed && signOf(value) > 0 ? '+' : ''
  return `${plus}${value.replace('.', ',')}%`
}
