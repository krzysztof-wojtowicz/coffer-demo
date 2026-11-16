import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LimitsSection } from './LimitsSection'

const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => Response) }))
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({
      baseUrl: 'http://localhost',
      fetch: (r: Request) => Promise.resolve(h.handler!(r)),
    }),
  }
})
const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { 'Content-Type': 'application/json' } })

let reqs: Request[]
let putResponse: () => Response
beforeEach(() => {
  reqs = []
  putResponse = () => json({ category_id: 1, category_name: 'Jedzenie', amount: '500.50' })
  h.handler = (req) => {
    const path = new URL(req.url).pathname
    if (path === '/api/categories')
      return json([
        { id: 1, name: 'Jedzenie', in_budget: true, is_default: true },
        { id: 9, name: 'Oszczędności', in_budget: false, is_default: true },
      ])
    if (path === '/api/budget/limits') return json([{ category_id: 1, category_name: 'Jedzenie', amount: '400.00' }])
    reqs.push(req)
    if (req.method === 'PUT') return putResponse()
    return new Response(null, { status: 204 })
  }
})
afterEach(cleanup)

function view() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <LimitsSection />
    </QueryClientProvider>,
  )
}

describe('LimitsSection', () => {
  it('saves with a dot decimal via PUT (only in_budget categories offered)', async () => {
    view()
    await screen.findByText('Jedzenie')
    await userEvent.click(screen.getByRole('button', { name: 'Edytuj' }))
    const input = screen.getByLabelText('Limit miesięczny') as HTMLInputElement
    await userEvent.clear(input)
    await userEvent.type(input, '500,50')
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz limit' }))
    await waitFor(() => expect(reqs.some((r) => r.method === 'PUT')).toBe(true))
    const put = reqs.find((r) => r.method === 'PUT')!
    expect(new URL(put.url).pathname).toBe('/api/budget/limits/1')
    expect(await put.json()).toEqual({ amount: '500.50' })
  })

  it('deletes only after confirmation', async () => {
    view()
    await screen.findByText('Jedzenie')
    await userEvent.click(screen.getByRole('button', { name: 'Usuń' }))
    expect(reqs.some((r) => r.method === 'DELETE')).toBe(false)
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Usuń' }))
    await waitFor(() => expect(reqs.some((r) => r.method === 'DELETE')).toBe(true))
  })

  it('shows the API 422 message', async () => {
    putResponse = () => json({ detail: 'Limit można ustawić tylko dla kategorii budżetowej' }, 422)
    view()
    await screen.findByText('Jedzenie')
    await userEvent.click(screen.getByRole('button', { name: 'Edytuj' }))
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz limit' }))
    expect(await screen.findByText(/tylko dla kategorii budżetowej/)).toBeTruthy()
  })
})
