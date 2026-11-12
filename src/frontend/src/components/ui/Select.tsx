import {
  Children,
  Fragment,
  isValidElement,
  useCallback,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
} from 'react'
import { cn } from '../../lib/cn'
import { controlClass } from './Input'
import { Popover } from './popover'

type Opt = { value: string; label: string; disabled: boolean }

function text(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(text).join('')
  if (isValidElement(node)) return text((node.props as { children?: ReactNode }).children)
  return ''
}

function parse(children: ReactNode): Opt[] {
  const out: Opt[] = []
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return
    const el = child as ReactElement<{ value?: string | number; disabled?: boolean; children?: ReactNode }>
    if (el.type === Fragment) {
      out.push(...parse(el.props.children))
    } else if (el.type === 'option') {
      const label = text(el.props.children)
      out.push({
        value: el.props.value != null ? String(el.props.value) : label,
        label,
        disabled: !!el.props.disabled,
      })
    }
  })
  return out
}

export type SelectProps = {
  value?: string | number
  onChange?: (e: { target: { value: string } }) => void
  children?: ReactNode
  disabled?: boolean
  required?: boolean
  id?: string
  className?: string
  'aria-label'?: string
}

export function Select({
  value,
  onChange,
  children,
  disabled,
  required,
  id,
  className,
  'aria-label': ariaLabel,
}: SelectProps) {
  const options = parse(children)
  const current = value == null ? '' : String(value)
  const selectedIdx = options.findIndex((o) => o.value === current)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const btnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  const btnId = id ?? `${listId}-btn`
  const close = useCallback(() => setOpen(false), [])

  const openList = () => {
    setActive(Math.max(selectedIdx, 0))
    setOpen(true)
  }
  const choose = (i: number) => {
    const o = options[i]
    if (!o || o.disabled) return
    onChange?.({ target: { value: o.value } })
    setOpen(false)
    btnRef.current?.focus()
  }
  const move = (from: number, step: number) => {
    let i = from
    for (let n = 0; n < options.length; n++) {
      i = Math.min(options.length - 1, Math.max(0, i + step))
      if (!options[i]?.disabled) return i
    }
    return from
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (disabled) return
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        openList()
      }
      return
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((a) => move(a, 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((a) => move(a, -1))
        break
      case 'Home':
        e.preventDefault()
        setActive(move(-1, 1))
        break
      case 'End':
        e.preventDefault()
        setActive(move(options.length, -1))
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        choose(active)
        break
      case 'Escape':
        e.preventDefault()
        e.stopPropagation()
        setOpen(false)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  const label = selectedIdx >= 0 ? options[selectedIdx].label : ''

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        id={btnId}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        aria-label={ariaLabel}
        aria-required={required || undefined}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKeyDown}
        className={cn(
          controlClass,
          'flex w-full items-center justify-between gap-2 text-left disabled:opacity-60',
          className,
        )}
      >
        <span className="truncate">{label}</span>
        <svg aria-hidden viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-muted" fill="currentColor">
          <path d="M5.5 7.5 10 12l4.5-4.5-1-1L10 10 6.5 6.5z" />
        </svg>
      </button>
      {open && (
        <Popover anchor={btnRef} panelRef={panelRef} onClose={close}>
          <ul id={listId} role="listbox" aria-label={ariaLabel} aria-labelledby={ariaLabel ? undefined : btnId} className="max-h-64 overflow-auto">
            {options.map((o, i) => (
              <li
                key={`${o.value}-${i}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === selectedIdx}
                aria-disabled={o.disabled || undefined}
                ref={(el) => {
                  if (el && i === active) el.scrollIntoView?.({ block: 'nearest' })
                }}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(i)}
                className={cn(
                  'flex items-center justify-between gap-3 rounded px-3 py-1.5 text-sm text-text',
                  i === active && 'bg-accent-soft',
                  i === selectedIdx && 'font-semibold text-accent',
                  o.disabled && 'opacity-50',
                )}
              >
                <span>{o.label}</span>
                {i === selectedIdx && <span aria-hidden>✓</span>}
              </li>
            ))}
          </ul>
        </Popover>
      )}
    </>
  )
}
