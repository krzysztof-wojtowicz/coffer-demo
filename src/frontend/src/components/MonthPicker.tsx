import { useEffect, useRef, useState } from 'react'
import { pl } from '../i18n/pl'
import { cn } from '../lib/cn'

function parse(value: string): { year: number; month: number } {
  const [y, m] = value.split('-').map(Number)
  return { year: y, month: m }
}
const fmt = (year: number, month: number) => `${year}-${String(month).padStart(2, '0')}`

function shift(value: string, delta: number): string {
  const { year, month } = parse(value)
  const idx = year * 12 + (month - 1) + delta
  return fmt(Math.floor(idx / 12), (idx % 12) + 1)
}

const arrow =
  'rounded-md px-2.5 py-1.5 text-text hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent'

export function MonthPicker({
  value,
  onChange,
  max,
}: {
  value: string
  onChange: (value: string) => void
  max?: string
}) {
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(parse(value).year)
  const ref = useRef<HTMLDivElement>(null)
  const { year: vy, month: vm } = parse(value)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [open])

  const nextDisabled = max !== undefined && shift(value, 1) > max
  const maxYear = max ? parse(max).year : undefined

  return (
    <div ref={ref} className="relative inline-flex items-center gap-1">
      <button
        type="button"
        aria-label={pl.monthPicker.prev}
        className={arrow}
        onClick={() => onChange(shift(value, -1))}
      >
        ‹
      </button>
      <button
        type="button"
        aria-label={pl.monthPicker.choose}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="min-w-40 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm font-medium capitalize hover:bg-border"
        onClick={() => {
          setYear(vy)
          setOpen((o) => !o)
        }}
      >
        {pl.monthPicker.months[vm - 1]} {vy}
      </button>
      <button
        type="button"
        aria-label={pl.monthPicker.next}
        className={arrow}
        disabled={nextDisabled}
        onClick={() => onChange(shift(value, 1))}
      >
        ›
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={pl.monthPicker.choose}
          className="absolute left-0 top-full z-20 mt-1 w-64 rounded-lg border border-border bg-surface p-3 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              aria-label={pl.monthPicker.prevYear}
              className={arrow}
              onClick={() => setYear((y) => y - 1)}
            >
              ‹
            </button>
            <span className="text-sm font-semibold">{year}</span>
            <button
              type="button"
              aria-label={pl.monthPicker.nextYear}
              className={arrow}
              disabled={maxYear !== undefined && year >= maxYear}
              onClick={() => setYear((y) => y + 1)}
            >
              ›
            </button>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {pl.monthPicker.short.map((name, i) => {
              const v = fmt(year, i + 1)
              const selected = v === value
              return (
                <button
                  key={name}
                  type="button"
                  aria-pressed={selected}
                  disabled={max !== undefined && v > max}
                  className={cn(
                    'rounded-md px-2 py-2 text-sm hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent',
                    selected && 'bg-accent font-semibold text-bg hover:bg-accent-strong',
                  )}
                  onClick={() => {
                    onChange(v)
                    setOpen(false)
                  }}
                >
                  {name}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
