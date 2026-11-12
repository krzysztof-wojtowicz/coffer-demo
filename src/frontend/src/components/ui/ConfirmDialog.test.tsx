import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

afterEach(cleanup)

const setup = (open = true) => {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(<ConfirmDialog open={open} title="Usunąć?" message="Na pewno" onConfirm={onConfirm} onCancel={onCancel} />)
  return { onConfirm, onCancel }
}

describe('ConfirmDialog', () => {
  it('nic nie renderuje gdy zamknięty', () => {
    setup(false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('ma role dialog, aria-modal i focus na Anuluj', () => {
    setup()
    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Anuluj' }))
  })

  it('Usuń potwierdza, Esc i tło anulują', async () => {
    const { onConfirm, onCancel } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Usuń' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    await userEvent.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('dialog').parentElement as HTMLElement)
    expect(onCancel).toHaveBeenCalledTimes(2)
  })
})
