import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SuggestionHistory } from './SuggestionHistory'

const mk = (id: number, action = 'portfolio_review') => ({
  id, action, source: 'rules', ai_status: 'ok', headline: `Sugestia ${id}`,
  report: { headline: `Sugestia ${id}`, facts: [], tables: [], findings: [], recommendations: [], risks: [], sources: [], disclaimer: 'x' },
  params: {}, model: null, provider: null, run_id: null, created_at: '2026-11-01T10:00:00Z', profile_used: false,
})
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } })
const urls: string[] = []

beforeEach(() => {
  urls.length = 0
  vi.stubGlobal('fetch', (url: string) => {
    if (url === '/api/agent/actions') return Promise.resolve(json([]))
    urls.push(url)
    const p = new URL(url, 'http://x').searchParams
    const offset = Number(p.get('offset'))
    const all = p.get('source') === 'ai' ? [] : [1, 2, 3, 4, 5, 6, 7]
    return Promise.resolve(json({ items: all.slice(offset, offset + 5).map((i) => mk(i, 'surplus')), total: all.length }))
  })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SuggestionHistory />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SuggestionHistory', () => {
  it('shows 5 items, loads more with offset=5, labels legacy actions', async () => {
    setup()
    expect(await screen.findByText('5 z 7')).toBeTruthy()
    expect(screen.getAllByText('Archiwalna: Nadwyżka')).toHaveLength(5)
    await userEvent.click(screen.getByRole('button', { name: 'Wyświetl więcej' }))
    expect(await screen.findByText('7 z 7')).toBeTruthy()
    expect(urls.some((u) => u.includes('offset=5') && u.includes('limit=5'))).toBe(true)
    expect(screen.queryByRole('button', { name: 'Wyświetl więcej' })).toBeNull()
  })

  it('changing the sort order resets the list to a fresh query', async () => {
    setup()
    await screen.findByText('5 z 7')
    await userEvent.click(screen.getByRole('button', { name: 'Wyświetl więcej' }))
    await screen.findByText('7 z 7')
    await userEvent.click(screen.getByRole('combobox', { name: /Sortowanie/ }))
    await userEvent.click(await screen.findByRole('option', { name: 'Najstarsze' }))
    await waitFor(() => expect(urls.some((u) => u.includes('order=asc') && u.includes('offset=0'))).toBe(true))
    await waitFor(() => expect(screen.getByText('5 z 7')).toBeTruthy())
  })
})
