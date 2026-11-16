import { pl } from '../i18n/pl'

export function validationText(type: string): string {
  if (type.includes('missing')) return pl.validation.required
  if (type.includes('decimal') || type.includes('number')) return pl.validation.invalidAmount
  if (type.includes('date')) return pl.validation.invalidDate
  return pl.validation.invalid
}

/** Zamienia ciało błędu API (detail: string | lista błędów walidacji) na polski komunikat. */
export function apiErrorMessage(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; type?: string }) => {
        const field = String(d.loc?.[d.loc.length - 1] ?? '')
        const name = pl.transactions.fieldNames[field] ?? field
        return `${name}: ${validationText(d.type ?? '')}`
      })
      .join('; ')
  }
  return pl.common.genericError
}
