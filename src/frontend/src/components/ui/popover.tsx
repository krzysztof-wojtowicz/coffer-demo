import { useEffect, useLayoutEffect, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'

type Pos = { top: number; left: number; minWidth: number }

/** Floating panel anchored under `anchor`, rendered in a portal (safe inside <label>). */
export function Popover({
  anchor,
  panelRef,
  onClose,
  children,
}: {
  anchor: RefObject<HTMLElement | null>
  panelRef: RefObject<HTMLDivElement | null>
  onClose: () => void
  children: ReactNode
}) {
  const [pos, setPos] = useState<Pos | null>(null)

  useLayoutEffect(() => {
    const update = () => {
      const el = anchor.current
      if (!el) return
      const r = el.getBoundingClientRect()
      setPos({ top: r.bottom + 4, left: r.left, minWidth: r.width })
    }
    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [anchor])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (anchor.current?.contains(t) || panelRef.current?.contains(t)) return
      onClose()
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [anchor, panelRef, onClose])

  if (!pos) return null
  return createPortal(
    <div
      ref={panelRef}
      style={{ position: 'fixed', top: pos.top, left: pos.left, minWidth: pos.minWidth, zIndex: 60 }}
      className="rounded-md border border-border bg-surface p-1 shadow-lg"
    >
      {children}
    </div>,
    document.body,
  )
}
