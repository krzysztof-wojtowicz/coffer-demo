import { formatMoney, signOf } from '../lib/format'
import { cn } from '../lib/cn'

// Plain amount, red when negative. Use <Signed> when positives should be green too.
export function Money({ value }: { value: string }) {
  return <span className={cn('font-mono tabular-nums', signOf(value) < 0 && 'text-negative')}>{formatMoney(value)}</span>
}
