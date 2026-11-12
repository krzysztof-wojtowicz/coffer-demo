import type { KeyboardEvent, ReactNode } from 'react'
import { pl } from '../i18n/pl'
import { cn } from '../lib/cn'
import { type ThemePreference, useTheme } from '../lib/theme'

const svgProps = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}
const icons: Record<ThemePreference, ReactNode> = {
  light: (
    <svg {...svgProps}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  dark: (
    <svg {...svgProps}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  ),
  system: (
    <svg {...svgProps}>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  ),
}

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
            aria-label={o.label}
            title={o.label}
            onClick={() => setPreference(o.value)}
            className={cn(
              'rounded p-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
              checked ? 'bg-accent-soft font-semibold text-accent ring-1 ring-accent' : 'text-muted hover:text-text',
            )}
          >
            {icons[o.value]}
          </button>
        )
      })}
    </div>
  )
}
