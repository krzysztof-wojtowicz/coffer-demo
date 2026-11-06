import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AccountPage } from './AccountPage'

const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => Promise<Response>) }))
vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) => {
  const req =
    input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
  return h.handler!(req)
})
// openapi-fetch needs an absolute base URL outside the browser.
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({ baseUrl: 'http://localhost', fetch: (r: Request) => globalThis.fetch(r) }),
  }
})
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let calls: { method: string; path: string; body: unknown }[]
let respond: (path: string) => Response

beforeEach(() => {
  calls = []
  respond = () => new Response(null, { status: 204 })
  h.handler = async (req) => {
    const path = new URL(req.url).pathname
    if (path === '/api/auth/me') return json({ id: 1, email: 'jan@example.com' })
    const text = await req.text()
    calls.push({ method: req.method, path, body: text ? JSON.parse(text) : null })
    return respond(path)
  }
})
afterEach(cleanup)

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/account']}>
        <Routes>
          <Route path="/account" element={<AccountPage />} />
          <Route path="/login" element={<p>strona logowania</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('AccountPage', () => {
  it('zmienia hasło po walidacji po stronie klienta', async () => {
    const user = renderPage()
    await user.type(await screen.findByLabelText('Obecne hasło'), 'Stare-haslo-123')
    await user.type(screen.getByLabelText('Nowe hasło'), 'krotkie')
    await user.click(screen.getByRole('button', { name: 'Zmień hasło' }))
    expect(screen.getByText('Hasło musi mieć co najmniej 12 znaków.')).toBeTruthy()
    expect(calls).toHaveLength(0)

    await user.clear(screen.getByLabelText('Nowe hasło'))
    await user.type(screen.getByLabelText('Nowe hasło'), 'Pies-w-kaloszach-7')
    await user.click(screen.getByRole('button', { name: 'Zmień hasło' }))
    expect(await screen.findByRole('status')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/auth/password' })
    expect(calls[0].body).toEqual({
      current_password: 'Stare-haslo-123',
      new_password: 'Pies-w-kaloszach-7',
    })
  })

  it('pokazuje błąd złego obecnego hasła', async () => {
    respond = () => json({ detail: 'Nieprawidłowe hasło' }, 403)
    const user = renderPage()
    await user.type(await screen.findByLabelText('Obecne hasło'), 'zle-haslo-123')
    await user.type(screen.getByLabelText('Nowe hasło'), 'Pies-w-kaloszach-7')
    await user.click(screen.getByRole('button', { name: 'Zmień hasło' }))
    expect(await screen.findByText('Nieprawidłowe hasło')).toBeTruthy()
  })

  it('wylogowuje ze wszystkich urządzeń', async () => {
    const user = renderPage()
    await user.click(await screen.findByRole('button', { name: 'Wyloguj ze wszystkich urządzeń' }))
    expect(await screen.findByText('strona logowania')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/auth/logout-all' })
  })

  it('usuwa konto po potwierdzeniu hasłem', async () => {
    const user = renderPage()
    await user.type(await screen.findByLabelText('Potwierdź hasłem'), 'Stare-haslo-123')
    await user.click(screen.getByRole('button', { name: 'Usuń konto na zawsze' }))
    expect(await screen.findByText('strona logowania')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/auth/account' })
    expect(calls[0].body).toEqual({ password: 'Stare-haslo-123' })
  })

  it('przy błędnym haśle nie usuwa i pokazuje komunikat', async () => {
    respond = () => json({ detail: 'Nieprawidłowe hasło' }, 403)
    const user = renderPage()
    await user.type(await screen.findByLabelText('Potwierdź hasłem'), 'zle')
    await user.click(screen.getByRole('button', { name: 'Usuń konto na zawsze' }))
    expect(await screen.findByText('Nieprawidłowe hasło')).toBeTruthy()
    expect(screen.queryByText('strona logowania')).toBeNull()
  })
})
