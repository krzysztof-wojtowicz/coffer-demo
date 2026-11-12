import { useCallback, useRef, useState, type KeyboardEvent } from 'react'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { isoDate, todayIso as getTodayIso } from '../../lib/date'
import { controlClass } from './Input'
import { Popover } from './popover'

const MONTHS = pl.datePicker.months
const DAYS = pl.datePicker.days

const iso = isoDate
function parseIso(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return iso(d) === s ? d : null
}
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)

export function DatePicker({
  value,
  onChange,
  required,
  id,
  disabled,
  min,
  max,
  'aria-label': ariaLabel,
}: {
  value: string
  onChange: (value: string) => void
  required?: boolean
  id?: string
  disabled?: boolean
  min?: string
  max?: string
  'aria-label'?: string
}) {
  const selected = parseIso(value)
  const [open, setOpen] = useState(false)
  const [focus, setFocus] = useState<Date>(selected ?? new Date())
  const btnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const close = useCallback(() => setOpen(false), [])
  const todayIso = getTodayIso()

  const openCal = () => {
    setFocus(parseIso(value) ?? new Date())
    setOpen(true)
  }
  const outOfRange = (k: string) => (min !== undefined && k < min) || (max !== undefined && k > max)
  const pick = (d: Date) => {
    if (outOfRange(iso(d))) return
    onChange(iso(d))
    setOpen(false)
    btnRef.current?.focus()
  }
  const shiftMonth = (n: number) =>
    setFocus((f) => {
      const last = new Date(f.getFullYear(), f.getMonth() + n + 1, 0).getDate()
      return new Date(f.getFullYear(), f.getMonth() + n, Math.min(f.getDate(), last))
    })

  const onKeyDown = (e: KeyboardEvent) => {
    if (disabled) return
    if (!open) {
      if (['ArrowDown', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        openCal()
      }
      return
    }
    const step: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }
    if (e.key in step) {
      e.preventDefault()
      setFocus((f) => addDays(f, step[e.key]))
    } else if (e.key === 'PageUp' || e.key === 'PageDown') {
      e.preventDefault()
      shiftMonth(e.key === 'PageUp' ? -1 : 1)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      pick(focus)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
      btnRef.current?.focus()
    } else if (e.key === 'Tab') {
      setOpen(false)
      btnRef.current?.focus()
    }
  }

  const onDialogKey = (e: KeyboardEvent) => {
    // Enter/Space on "Dziś" / "Wyczyść" / month arrows keep their own button behaviour.
    if ((e.key === 'Enter' || e.key === ' ') && (e.target as HTMLElement).getAttribute('role') !== 'gridcell') return
    onKeyDown(e)
  }

  const first = new Date(focus.getFullYear(), focus.getMonth(), 1)
  const offset = (first.getDay() + 6) % 7
  const cells = Array.from({ length: 42 }, (_, i) => addDays(first, i - offset))
  const focusIso = iso(focus)
  const weeks = Array.from({ length: 6 }, (_, w) => cells.slice(w * 7, w * 7 + 7))

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        id={id}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-required={required || undefined}
        onClick={() => (open ? setOpen(false) : openCal())}
        onKeyDown={onKeyDown}
        className={cn(controlClass, 'flex w-full items-center justify-between gap-2 text-left disabled:opacity-60')}
      >
        <span className={selected ? '' : 'text-muted'}>{selected ? value : pl.datePicker.choose}</span>
        <svg aria-hidden viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-muted" fill="currentColor">
          <path d="M6 2v2H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1h-2V2h-2v2H8V2zM5 8h10v7H5z" />
        </svg>
      </button>
      {open && (
        <Popover anchor={btnRef} panelRef={panelRef} onClose={close}>
          <div role="dialog" aria-label={pl.datePicker.calendar} onKeyDown={onDialogKey} className="w-64 p-2 text-sm text-text">
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                aria-label={pl.datePicker.prevMonth}
                className="rounded px-2 py-1 hover:bg-surface-2"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => shiftMonth(-1)}
              >
                ‹
              </button>
              <span className="font-medium" aria-live="polite">
                {MONTHS[focus.getMonth()]} {focus.getFullYear()}
              </span>
              <button
                type="button"
                aria-label={pl.datePicker.nextMonth}
                className="rounded px-2 py-1 hover:bg-surface-2"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => shiftMonth(1)}
              >
                ›
              </button>
            </div>
            <div role="grid" aria-label={`${MONTHS[focus.getMonth()]} ${focus.getFullYear()}`}>
              <div role="row" className="grid grid-cols-7 text-center text-xs text-muted">
                {DAYS.map((d) => (
                  <span key={d} role="columnheader" className="py-1">
                    {d}
                  </span>
                ))}
              </div>
              {weeks.map((week) => (
                <div key={iso(week[0])} role="row" className="mt-0.5 grid grid-cols-7 gap-0.5">
                  {week.map((d) => {
                    const k = iso(d)
                    const inMonth = d.getMonth() === focus.getMonth()
                    const off = outOfRange(k)
                    const active = k === focusIso
                    return (
                      <button
                        key={k}
                        type="button"
                        role="gridcell"
                        aria-selected={k === value}
                        disabled={off}
                        tabIndex={active ? 0 : -1}
                        ref={(el) => {
                          // Real DOM focus follows the active day, so screen readers announce it.
                          if (el && active && document.activeElement !== el) el.focus()
                        }}
                        aria-current={k === todayIso ? 'date' : undefined}
                        aria-label={`${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => pick(d)}
                        className={cn(
                          'rounded py-1 text-center hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent',
                          !inMonth && 'text-muted opacity-60',
                          k === todayIso && 'border border-accent',
                          active && 'ring-2 ring-accent',
                          k === value && 'bg-accent font-semibold text-bg hover:bg-accent',
                        )}
                      >
                        {d.getDate()}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between">
              <button
                type="button"
                className="rounded px-2 py-1 text-accent hover:bg-surface-2"
                onMouseDown={(e) => e.preventDefault()}
                disabled={outOfRange(todayIso)}
                onClick={() => pick(new Date())}
              >
                {pl.datePicker.today}
              </button>
              {!required && (
                <button
                  type="button"
                  className="rounded px-2 py-1 text-muted hover:bg-surface-2"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange('')
                    setOpen(false)
                    btnRef.current?.focus()
                  }}
                >
                  {pl.datePicker.clear}
                </button>
              )}
            </div>
          </div>
        </Popover>
      )}
    </>
  )
}
