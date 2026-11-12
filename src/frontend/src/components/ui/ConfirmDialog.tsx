import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { pl } from '../../i18n/pl'
import { Button } from './Button'

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = pl.common.delete,
  cancelLabel = pl.common.cancel,
  danger = true,
  pending,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    cancelRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-sm space-y-3 rounded-lg border border-border bg-surface p-5 shadow-xl"
      >
        <h2 id="confirm-title" className="text-lg font-semibold text-text">
          {title}
        </h2>
        {message && <p className="text-sm text-muted">{message}</p>}
        <div className="flex justify-end gap-2">
          <Button ref={cancelRef} type="button" variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={danger ? 'danger' : 'primary'}
            loading={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
