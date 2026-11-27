import { useEffect, useLayoutEffect, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'

type Pos = { top?: number; bottom?: number; left: number; minWidth: number; maxHeight: number }

const GAP = 4
const MARGIN = 8

/** Floating panel anchored to `anchor`: opens below, flips above when there is more room there. */
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
      const spaceBelow = window.innerHeight - r.bottom - MARGIN
      const spaceAbove = r.top - MARGIN
      // Natural height is only known once the panel is mounted; before that, prefer below.
      const panel = panelRef.current
      const natural = panel ? panel.scrollHeight : 0
      const below = natural <= spaceBelow || spaceBelow >= spaceAbove
      const width = panel?.offsetWidth ?? r.width
      const left = Math.max(MARGIN, Math.min(r.left, window.innerWidth - width - MARGIN))
      setPos({
        ...(below ? { top: r.bottom + GAP } : { bottom: window.innerHeight - r.top + GAP }),
        left,
        minWidth: r.width,
        maxHeight: Math.max(0, (below ? spaceBelow : spaceAbove) - GAP),
      })
    }
    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [anchor, panelRef])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (anchor.current?.contains(t) || panelRef.current?.contains(t)) return
      onClose()
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [anchor, panelRef, onClose])

  // First render mounts the panel hidden so it can be measured; the layout effect then positions it before paint.
  return createPortal(
    <div
      ref={panelRef}
      style={{
        position: 'fixed',
        ...pos,
        visibility: pos ? 'visible' : 'hidden',
        zIndex: 60,
        overflowY: 'auto',
      }}
      className="rounded bg-surface-2 p-1 shadow-xl ring-1 ring-border"
    >
      {children}
    </div>,
    document.body,
  )
}
