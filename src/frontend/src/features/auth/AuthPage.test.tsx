import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthPage } from './AuthPage'

const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => Response) }))
vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) => {
  const req =
    input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
  return Promise.resolve(h.handler!(req))
})
// openapi-fetch needs an absolute base URL outside the browser.
vi.mock('../../api/client', async () => {
  const { default: createClient } = await import('openapi-fetch')
  return {
    api: createClient({ baseUrl: 'http://localhost', fetch: (r: Request) => globalThis.fetch(r) }),
  }
})
const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })

let calls: Request[]
let postResponse: () => Response

beforeEach(() => {
  calls = []
  postResponse = () => json({ id: 1, email: 'jan@example.com' }, 201)
  h.handler = (req) => {
    if (req.url.endsWith('/api/auth/me')) return json({ detail: 'Wymagane logowanie' }, 401)
    calls.push(req)
    return postResponse()
  }
})
afterEach(cleanup)

function renderPage(mode: 'login' | 'register') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthPage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('AuthPage: rejestracja', () => {
  it('pokazuje niespełnione zasady i nie wysyła słabego hasła', async () => {
    const user = renderPage('register')
    await user.type(await screen.findByLabelText('E-mail'), 'jan@example.com')
    await user.type(screen.getByLabelText('Hasło'), 'password1234')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Załóż konto' }))
    expect(screen.getByText('To hasło jest zbyt popularne. Wybierz inne.')).toBeTruthy()
    expect(calls).toHaveLength(0)
  })

  it('wymaga akceptacji przechowywania danych', async () => {
    const user = renderPage('register')
    await user.type(await screen.findByLabelText('E-mail'), 'jan@example.com')
    await user.type(screen.getByLabelText('Hasło'), 'Kot-w-butach-42')
    await user.click(screen.getByRole('button', { name: 'Załóż konto' }))
    expect(
      screen.getByText('Bez akceptacji przechowywania danych nie możemy założyć konta.'),
    ).toBeTruthy()
    expect(calls).toHaveLength(0)
  })

  it('pokazuje siłę hasła i rejestruje jednym żądaniem', async () => {
    const user = renderPage('register')
    await user.type(await screen.findByLabelText('E-mail'), 'jan@example.com')
    await user.type(screen.getByLabelText('Hasło'), 'Kot-w-butach-42-i-pies')
    expect(screen.getByRole('meter').getAttribute('aria-valuetext')).toBe('Silne')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Załóż konto' }))
    await vi.waitFor(() => expect(calls).toHaveLength(1))
    expect(new URL(calls[0].url).pathname).toBe('/api/auth/register')
  })
})

describe('AuthPage: logowanie', () => {
  it('pokazuje komunikat 429 z serwera', async () => {
    postResponse = () =>
      json({ detail: 'Zbyt wiele prób. Spróbuj ponownie za 15 min.' }, 429, {
        'Retry-After': '900',
      })
    const user = renderPage('login')
    await user.type(await screen.findByLabelText('E-mail'), 'jan@example.com')
    await user.type(screen.getByLabelText('Hasło'), 'cokolwiek')
    await user.click(screen.getByRole('button', { name: 'Zaloguj' }))
    expect(await screen.findByText('Zbyt wiele prób. Spróbuj ponownie za 15 min.')).toBeTruthy()
  })

  it('nie stosuje polityki haseł przy logowaniu (stare konta)', async () => {
    postResponse = () => json({ id: 1, email: 'jan@example.com' })
    const user = renderPage('login')
    await user.type(await screen.findByLabelText('E-mail'), 'jan@example.com')
    await user.type(screen.getByLabelText('Hasło'), 'krotkie')
    await user.click(screen.getByRole('button', { name: 'Zaloguj' }))
    await vi.waitFor(() => expect(calls).toHaveLength(1))
    expect(screen.queryByRole('meter')).toBeNull()
  })
})
