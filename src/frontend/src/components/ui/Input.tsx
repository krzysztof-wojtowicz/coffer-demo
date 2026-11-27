import type { InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export const controlClass =
  'rounded bg-surface-2 px-3 py-2 text-sm font-normal text-text placeholder:text-muted hover:brightness-125 focus:outline-none focus:ring-2 focus:ring-accent aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-negative'

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={cn(controlClass, className)} />
}
