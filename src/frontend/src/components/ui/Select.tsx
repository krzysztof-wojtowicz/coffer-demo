import type { SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'
import { controlClass } from './Input'

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={cn(controlClass, className)} />
}
