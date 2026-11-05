import { formatMoney } from '../lib/money'
import { cn } from '../lib/cn'

export function Money({ value, colored = false }: { value: string; colored?: boolean }) {
  const neg = value.startsWith('-')
  const zero = /^[-+]?0*[.,]?0*$/.test(value)
  return (
    <span
      className={cn(
        'tabular-nums',
        neg && 'text-negative',
        colored && !neg && !zero && 'text-positive',
      )}
    >
      {formatMoney(value)}
    </span>
  )
}
