import type { InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export const controlClass =
  'rounded-md border border-border bg-surface-2 px-3 py-2 text-sm font-normal text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40'

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={cn(controlClass, className)} />
}
