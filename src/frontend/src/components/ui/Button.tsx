import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'
import { Spinner } from './Spinner'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
}

const variants = {
  primary: 'bg-accent text-bg hover:bg-accent-strong',
  secondary: 'border border-border bg-surface-2 text-text hover:bg-border',
  ghost: 'text-text hover:bg-surface-2',
  danger: 'bg-negative text-bg hover:bg-negative/90',
}
const sizes = { sm: 'px-2 py-1 text-sm', md: 'px-3.5 py-2 text-sm' }

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  disabled,
  onClick,
  type = 'button',
  children,
  ...rest
}: Props) {
  return (
    <button
      type={type}
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      onClick={loading ? undefined : onClick}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60',
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading && <Spinner className="size-3.5" />}
      {children}
    </button>
  )
}
