import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ActionReport } from './ActionReport'
import type { Report } from './queries'

const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => Response) }))
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return { api: createClient({ baseUrl: 'http://localhost', fetch: (r: Request) => Promise.resolve(h.handler!(r)) }) }
})
const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { 'Content-Type': 'application/json' } })

const report: Report = {
  headline: 'Plan',
  facts: [],
  findings: [],
  recommendations: [],
  risks: [],
  sources: [],
  disclaimer: 'x',
  tables: [
    {
      id: 'proposed_limits',
      title: 'Limity',
      columns: [{ key: 'category', label: 'Kategoria', kind: 'text' }],
      rows: [
        { category: 'Jedzenie', proposed_limit: '500.00', category_id: '1' },
        { category: 'Transport', proposed_limit: '200.50', category_id: '2' },
      ],
    },
  ],
}

let puts: Request[]
let fail: boolean
beforeEach(() => {
  puts = []
  fail = false
  h.handler = (req) => {
    puts.push(req)
    return fail
      ? json({ detail: 'Limit można ustawić tylko dla kategorii budżetowej' }, 422)
      : json({ category_id: 1, category_name: 'x', amount: '1.00' })
  }
})
afterEach(cleanup)

function view(action = 'budget_plan') {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ActionReport report={report} source="rules" action={action} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ApplyLimits', () => {
  it('is hidden for other actions', () => {
    view('portfolio_review')
    expect(screen.queryByRole('button', { name: 'Ustaw proponowane limity' })).toBeNull()
  })

  it('confirms, then PUTs each limit and reports success', async () => {
    view()
    await userEvent.click(screen.getByRole('button', { name: 'Ustaw proponowane limity' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog.textContent).toContain('Jedzenie')
    expect(puts).toHaveLength(0)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Ustaw limity' }))
    await screen.findByText('Ustawiono limity: 2.')
    expect(puts.map((r) => new URL(r.url).pathname).sort()).toEqual([
      '/api/budget/limits/1',
      '/api/budget/limits/2',
    ])
    expect(await puts.find((r) => r.url.endsWith('/2'))!.json()).toEqual({ amount: '200.50' })
  })

  it('shows a Polish error when saving fails', async () => {
    fail = true
    view()
    await userEvent.click(screen.getByRole('button', { name: 'Ustaw proponowane limity' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Ustaw limity' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Nie udało się ustawić'))
  })
})
