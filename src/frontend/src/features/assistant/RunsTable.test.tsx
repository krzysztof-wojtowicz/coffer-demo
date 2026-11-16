import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RunsTable } from './RunsTable'

const run = {
  id: 1, action: 'portfolio_review', status: 'ok', provider: 'anthropic', model: 'claude-x', llm_calls: 1,
  tool_calls_count: 2, input_tokens: 100, output_tokens: 50, cost_usd: '0.0123', duration_ms: 2500,
  created_at: '2026-11-01T10:00:00Z', suggestion_id: null,
}
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } })
const urls: string[] = []

beforeEach(() => {
  urls.length = 0
  vi.stubGlobal('fetch', (url: string) => {
    if (url === '/api/agent/actions') return Promise.resolve(json([]))
    urls.push(url)
    return Promise.resolve(json({ items: [run, { ...run, id: 2, provider: null, cost_usd: null }], total: 2 }))
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('RunsTable', () => {
  it('renders provider/cost labels and sorting changes query params and aria-sort', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <RunsTable />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findAllByText('Claude')).toHaveLength(1)
    expect(screen.getByText('~$0.01')).toBeTruthy()
    const th = screen.getByRole('columnheader', { name: /Koszt/ })
    expect(th.getAttribute('aria-sort')).toBe('none')
    await userEvent.click(screen.getByRole('button', { name: /Koszt/ }))
    await waitFor(() => expect(urls.some((u) => u.includes('sort=cost_usd') && u.includes('order=desc'))).toBe(true))
    expect(screen.getByRole('columnheader', { name: /Koszt/ }).getAttribute('aria-sort')).toBe('descending')
    await userEvent.click(screen.getByRole('button', { name: /Koszt/ }))
    await waitFor(() => expect(urls.some((u) => u.includes('sort=cost_usd') && u.includes('order=asc'))).toBe(true))
  })
})
