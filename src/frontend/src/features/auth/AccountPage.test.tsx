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
    if (path === '/api/auth/me' && req.method === 'GET') return json({ id: 1, email: 'jan@example.com', display_name: 'Jan' })
    if (path === '/api/profile') return json(null)
    if (path === '/api/cash/opening-balance') return json(null)
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

/** Settings rows are collapsed; open one and wait for a control inside it. */
async function openRow(user: ReturnType<typeof userEvent.setup>, row: string | RegExp) {
  await user.click(await screen.findByRole('button', { name: row }))
}
async function openAndFind(user: ReturnType<typeof userEvent.setup>, row: string | RegExp, label: string) {
  await openRow(user, row)
  return screen.findByLabelText(label)
}

describe('AccountPage', () => {
  it('zmienia imię przez PATCH i odrzuca puste', async () => {
    respond = () => json({ id: 1, email: 'jan@example.com', display_name: 'Janek' })
    const user = renderPage()
    const input = (await openAndFind(user, /^Imię/, 'Imię')) as HTMLInputElement
    expect(input.value).toBe('Jan')
    await user.clear(input)
    await user.type(input, '   ')
    await user.click(screen.getByRole('button', { name: 'Zapisz imię' }))
    expect(await screen.findByText('Imię musi mieć od 1 do 50 znaków')).toBeTruthy()
    expect(calls).toHaveLength(0)
    await user.clear(input)
    await user.type(input, ' Janek ')
    await user.click(screen.getByRole('button', { name: 'Zapisz imię' }))
    expect(await screen.findByRole('status')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/auth/me', body: { display_name: 'Janek' } })
  })

  it('otwiera jeden wiersz naraz, Escape zamyka', async () => {
    const user = renderPage()
    await openRow(user, /^Hasło/)
    expect(screen.getByLabelText('Obecne hasło')).toBeTruthy()
    await openRow(user, /^Sesje/)
    expect(screen.queryByLabelText('Obecne hasło')).toBeNull()
    expect(screen.getByRole('button', { name: 'Wyloguj ze wszystkich urządzeń' })).toBeTruthy()
    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: /^Sesje/ }).getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('Bezpieczeństwo konta')).toBeNull()
  })

  it('zmienia hasło po walidacji po stronie klienta', async () => {
    const user = renderPage()
    await user.type(await openAndFind(user, /^Hasło/, 'Obecne hasło'), 'Stare-haslo-123')
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
    await user.type(await openAndFind(user, /^Hasło/, 'Obecne hasło'), 'zle-haslo-123')
    await user.type(screen.getByLabelText('Nowe hasło'), 'Pies-w-kaloszach-7')
    await user.click(screen.getByRole('button', { name: 'Zmień hasło' }))
    expect(await screen.findByText('Nieprawidłowe hasło')).toBeTruthy()
  })

  it('wylogowuje ze wszystkich urządzeń', async () => {
    const user = renderPage()
    await openRow(user, /^Sesje/)
    await user.click(await screen.findByRole('button', { name: 'Wyloguj ze wszystkich urządzeń' }))
    expect(await screen.findByText('strona logowania')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/auth/logout-all' })
  })

  it('usuwa konto po potwierdzeniu hasłem', async () => {
    const user = renderPage()
    await user.type(await openAndFind(user, 'Usuń konto', 'Potwierdź hasłem'), 'Stare-haslo-123')
    await user.click(screen.getByRole('button', { name: 'Usuń konto na zawsze' }))
    expect(await screen.findByText('strona logowania')).toBeTruthy()
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/auth/account' })
    expect(calls[0].body).toEqual({ password: 'Stare-haslo-123' })
  })

  it('przy błędnym haśle nie usuwa i pokazuje komunikat', async () => {
    respond = () => json({ detail: 'Nieprawidłowe hasło' }, 403)
    const user = renderPage()
    await user.type(await openAndFind(user, 'Usuń konto', 'Potwierdź hasłem'), 'zle')
    await user.click(screen.getByRole('button', { name: 'Usuń konto na zawsze' }))
    expect(await screen.findByText('Nieprawidłowe hasło')).toBeTruthy()
    expect(screen.queryByText('strona logowania')).toBeNull()
  })
})


describe("AccountPage: dodatkowe przypadki", () => {
  it("nowe hasło równe obecnemu jest blokowane bez żądania", async () => {
    const user = renderPage();
    await user.type(
      await openAndFind(user, /^Hasło/, 'Obecne hasło'),
      "Kot-w-butach-42",
    );
    await user.type(screen.getByLabelText("Nowe hasło"), "Kot-w-butach-42");
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));
    expect(calls).toHaveLength(0);
  });

  it("zmiana hasła stosuje regułę e-maila zalogowanego użytkownika", async () => {
    const user = renderPage();
    await user.type(
      await openAndFind(user, /^Hasło/, 'Obecne hasło'),
      "Kot-w-butach-42",
    );
    await screen.findByText("Ustawienia");
    await vi.waitFor(async () => {
      await user.clear(screen.getByLabelText("Nowe hasło"));
      await user.type(screen.getByLabelText("Nowe hasło"), "jan@example.com");
      expect(
        screen.getByText("Hasło nie może być takie samo jak adres e-mail."),
      ).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));
    expect(calls).toHaveLength(0);
  });

  it("429 przy usuwaniu konta: komunikat i brak wylogowania", async () => {
    respond = () =>
      new Response(
        JSON.stringify({
          detail: "Zbyt wiele prób. Spróbuj ponownie za 15 min.",
        }),
        {
          status: 429,
          headers: { "Content-Type": "application/json", "Retry-After": "900" },
        },
      );
    const user = renderPage();
    await user.type(
      await openAndFind(user, 'Usuń konto', 'Potwierdź hasłem'),
      "Kot-w-butach-42",
    );
    await user.click(
      screen.getByRole("button", { name: "Usuń konto na zawsze" }),
    );
    expect(
      await screen.findByText("Zbyt wiele prób. Spróbuj ponownie za 15 min."),
    ).toBeTruthy();
    expect(screen.queryByText("strona logowania")).toBeNull();
  });

  it("błąd wylogowania wszędzie zostawia użytkownika na stronie", async () => {
    respond = () => json({ detail: "Wymagane logowanie" }, 401);
    const user = renderPage();
    await openRow(user, /^Sesje/);
    await user.click(await screen.findByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }));
    expect(await screen.findByText("Wymagane logowanie")).toBeTruthy();
  });

  it("pusta zgoda hasłem nie usuwa konta", async () => {
    const user = renderPage();
    await openRow(user, "Usuń konto");
    await user.click(await screen.findByRole("button", { name: "Usuń konto na zawsze" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
  });

  // BUG (medium, accounts/front, queries.ts useLeave): an error response with an empty body
  // (e.g. proxy 502/503/429) counts as success: the user is signed out locally and sent to
  // /login although the account was NOT deleted.
  it(
    "pusta odpowiedź błędu przy usuwaniu nie udaje sukcesu",
    async () => {
      respond = () =>
        new Response(null, { status: 503, headers: { "Content-Length": "0" } });
      const user = renderPage();
      await user.type(
        await openAndFind(user, 'Usuń konto', 'Potwierdź hasłem'),
        "Kot-w-butach-42",
      );
      await user.click(
        screen.getByRole("button", { name: "Usuń konto na zawsze" }),
      );
      await new Promise((r) => setTimeout(r, 100));
      expect(screen.queryByText("strona logowania")).toBeNull();
    },
  );
});
