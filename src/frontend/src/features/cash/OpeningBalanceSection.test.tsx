import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OpeningBalanceSection } from './OpeningBalanceSection'

vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({ baseUrl: 'http://localhost', fetch: (r: Request) => globalThis.fetch(r) }),
  }
})

let stored: { amount: string; as_of: string } | null
let calls: { method: string; body: unknown }[]
const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { 'Content-Type': 'application/json' } })

beforeEach(() => {
  stored = { amount: '1500.00', as_of: '2026-01-05' }
  calls = []
  vi.stubGlobal('fetch', async (req: Request) => {
    const method = req.method
    if (method === 'GET') return json(stored)
    const text = await req.text()
    calls.push({ method, body: text ? JSON.parse(text) : null })
    if (method === 'DELETE') {
      stored = null
      return new Response(null, { status: 204 })
    }
    stored = JSON.parse(text)
    return json(stored)
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <OpeningBalanceSection />
    </QueryClientProvider>,
  )
}

describe('OpeningBalanceSection', () => {
  it('prefills saved balance and saves a new amount', async () => {
    renderIt()
    const input = await screen.findByLabelText('Saldo (PLN)')
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('1500,00'))
    await userEvent.clear(input)
    await userEvent.type(input, '2000,50')
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    await screen.findByText('Saldo zapisane.')
    expect(calls[0]).toEqual({ method: 'PUT', body: { amount: '2000.50', as_of: '2026-01-05' } })
  })

  it('rejects an invalid amount without calling the API', async () => {
    renderIt()
    const input = await screen.findByLabelText('Saldo (PLN)')
    await userEvent.clear(input)
    await userEvent.type(input, 'abc')
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    expect(await screen.findByText('Podaj poprawną kwotę, np. 1234,56.')).toBeTruthy()
    expect(calls).toHaveLength(0)
  })

  it('deletes after confirmation', async () => {
    renderIt()
    await screen.findByLabelText('Saldo (PLN)')
    await userEvent.click(await screen.findByRole('button', { name: 'Usuń' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(dialog.querySelector('button:last-of-type') as HTMLElement)
    await waitFor(() => expect(calls[0]?.method).toBe('DELETE'))
  })
})
