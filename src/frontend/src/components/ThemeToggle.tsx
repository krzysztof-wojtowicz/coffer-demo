import type { KeyboardEvent } from 'react'
import { pl } from '../i18n/pl'
import { cn } from '../lib/cn'
import { type ThemePreference, useTheme } from '../lib/theme'

const options: { value: ThemePreference; label: string }[] = [
  { value: 'light', label: pl.theme.light },
  { value: 'dark', label: pl.theme.dark },
  { value: 'system', label: pl.theme.system },
]

export function ThemeToggle() {
  const { preference, setPreference } = useTheme()

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const i = options.findIndex((o) => o.value === preference)
    let n = i
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = (i + 1) % options.length
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = (i - 1 + options.length) % options.length
    else if (e.key === 'Home') n = 0
    else if (e.key === 'End') n = options.length - 1
    else return
    e.preventDefault()
    setPreference(options[n].value)
    e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]')[n]?.focus()
  }

  return (
    <div
      role="radiogroup"
      aria-label={pl.theme.label}
      onKeyDown={onKeyDown}
      className="flex rounded-md border border-border bg-surface-2 p-0.5"
    >
      {options.map((o) => {
        const checked = o.value === preference
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            onClick={() => setPreference(o.value)}
            className={cn(
              'rounded px-2 py-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
              checked ? 'bg-accent-soft font-semibold text-accent ring-1 ring-accent' : 'text-muted hover:text-text',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
