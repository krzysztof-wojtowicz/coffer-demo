import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { DatePicker } from './DatePicker'

afterEach(cleanup)

function Harness({ required, initial = '2026-03-15' }: { required?: boolean; initial?: string }) {
  const [v, setV] = useState(initial)
  return <DatePicker aria-label="Data" required={required} value={v} onChange={setV} />
}

describe('DatePicker', () => {
  it('pokazuje wartość i otwiera kalendarz z polskim miesiącem', async () => {
    render(<Harness />)
    const btn = screen.getByRole('button', { name: 'Data' })
    expect(btn.textContent).toContain('2026-03-15')
    await userEvent.click(btn)
    expect(screen.getByText('Marzec 2026')).toBeTruthy()
    expect(screen.getByText('Pn')).toBeTruthy()
  })

  it('nawigacja miesiącami i wybór dnia', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Data' }))
    await userEvent.click(screen.getByRole('button', { name: 'Następny miesiąc' }))
    expect(screen.getByText('Kwiecień 2026')).toBeTruthy()
    await userEvent.click(screen.getByRole('gridcell', { name: '10 Kwiecień 2026' }))
    expect(screen.getByRole('button', { name: 'Data' }).textContent).toContain('2026-04-10')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Wyczyść tylko gdy nie required', async () => {
    const { unmount } = render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Data' }))
    await userEvent.click(screen.getByRole('button', { name: 'Wyczyść' }))
    expect(screen.getByRole('button', { name: 'Data' }).textContent).toContain('Wybierz datę')
    unmount()
    render(<Harness required />)
    await userEvent.click(screen.getByRole('button', { name: 'Data' }))
    expect(screen.queryByRole('button', { name: 'Wyczyść' })).toBeNull()
  })

  it('klawiatura: strzałka, Enter i Esc', async () => {
    render(<Harness />)
    screen.getByRole('button', { name: 'Data' }).focus()
    await userEvent.keyboard('{Enter}{ArrowRight}{Enter}')
    expect(screen.getByRole('button', { name: 'Data' }).textContent).toContain('2026-03-16')
    await userEvent.keyboard('{Enter}{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('ARIA: komórki w wierszach, fokus na aktywnym dniu przy strzałkach', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Data' }))
    const cell = screen.getByRole('gridcell', { name: '15 Marzec 2026' })
    expect(cell.parentElement?.getAttribute('role')).toBe('row')
    expect(document.activeElement).toBe(cell)
    await userEvent.keyboard('{ArrowRight}')
    expect(document.activeElement).toBe(screen.getByRole('gridcell', { name: '16 Marzec 2026' }))
    await userEvent.keyboard('{ArrowDown}')
    expect(document.activeElement).toBe(screen.getByRole('gridcell', { name: '23 Marzec 2026' }))
  })

  it('min/max: dni poza zakresem są wyłączone i nie dają się wybrać', async () => {
    function Bounded() {
      const [v, setV] = useState('2026-03-15')
      return <DatePicker aria-label="Data" value={v} onChange={setV} min="2026-03-10" max="2026-03-20" />
    }
    render(<Bounded />)
    await userEvent.click(screen.getByRole('button', { name: 'Data' }))
    const before = screen.getByRole('gridcell', { name: '9 Marzec 2026' }) as HTMLButtonElement
    const after = screen.getByRole('gridcell', { name: '21 Marzec 2026' }) as HTMLButtonElement
    expect(before.disabled).toBe(true)
    expect(after.disabled).toBe(true)
    expect((screen.getByRole('gridcell', { name: '10 Marzec 2026' }) as HTMLButtonElement).disabled).toBe(false)
    await userEvent.click(before)
    expect(screen.getByRole('button', { name: 'Data' }).textContent).toContain('2026-03-15')
  })
})
