import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { Select } from './Select'

afterEach(cleanup)

function Harness({ onValue }: { onValue?: (v: string) => void }) {
  const [v, setV] = useState('b')
  return (
    <Select
      aria-label="Kolor"
      value={v}
      onChange={(e) => {
        setV(e.target.value)
        onValue?.(e.target.value)
      }}
    >
      <option value="a">Alfa</option>
      <option value="b">Beta</option>
      <option value="c">Gamma</option>
    </Select>
  )
}

describe('Select', () => {
  it('pokazuje zaznaczoną etykietę i otwiera listę z ARIA', async () => {
    render(<Harness />)
    const box = screen.getByRole('combobox', { name: 'Kolor' })
    expect(box.textContent).toContain('Beta')
    await userEvent.click(box)
    expect(screen.getByRole('listbox')).toBeTruthy()
    expect(screen.getByRole('option', { name: /Beta/ }).getAttribute('aria-selected')).toBe('true')
  })

  it('wybór kliknięciem woła onChange i zamyka listę', async () => {
    const seen: string[] = []
    render(<Harness onValue={(v) => seen.push(v)} />)
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(screen.getByRole('option', { name: /Gamma/ }))
    expect(seen).toEqual(['c'])
    expect(screen.queryByRole('listbox')).toBeNull()
    expect(screen.getByRole('combobox').textContent).toContain('Gamma')
  })

  it('obsługuje klawiaturę: strzałki, Home, Enter, Esc', async () => {
    const seen: string[] = []
    render(<Harness onValue={(v) => seen.push(v)} />)
    screen.getByRole('combobox').focus()
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(seen).toEqual(['c'])
    await userEvent.keyboard('{Enter}{Home}{Enter}')
    expect(seen).toEqual(['c', 'a'])
    await userEvent.keyboard('{Enter}{Escape}')
    expect(screen.queryByRole('listbox')).toBeNull()
    expect(seen).toEqual(['c', 'a'])
  })

  it('zamyka się po kliknięciu poza', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(document.body)
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('disabled nie otwiera', async () => {
    render(
      <Select value="a" disabled aria-label="X">
        <option value="a">A</option>
      </Select>,
    )
    await userEvent.click(screen.getByRole('combobox'))
    expect(screen.queryByRole('listbox')).toBeNull()
  })
})
