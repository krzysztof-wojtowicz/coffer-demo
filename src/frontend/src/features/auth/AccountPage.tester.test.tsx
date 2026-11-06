import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountPage } from "./AccountPage";

const h = vi.hoisted(() => ({
  handler: null as null | ((req: Request) => Promise<Response>),
}));
vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
  const req =
    input instanceof Request
      ? input
      : new Request(new URL(String(input), "http://localhost"), init);
  return h.handler!(req);
});
// openapi-fetch needs an absolute base URL outside the browser.
vi.mock("../../api/client", async () => {
  const { default: createClient } = await import("openapi-fetch");
  return {
    api: createClient({
      baseUrl: "http://localhost",
      fetch: (r: Request) => globalThis.fetch(r),
    }),
  };
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

let calls: { method: string; path: string; body: unknown }[];
let respond: (path: string) => Response;

beforeEach(() => {
  calls = [];
  respond = () => new Response(null, { status: 204 });
  h.handler = async (req) => {
    const path = new URL(req.url).pathname;
    if (path === "/api/auth/me")
      return json({ id: 1, email: "jan@example.com" });
    const text = await req.text();
    calls.push({
      method: req.method,
      path,
      body: text ? JSON.parse(text) : null,
    });
    return respond(path);
  };
});
afterEach(cleanup);

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route path="/account" element={<AccountPage />} />
          <Route path="/login" element={<p>strona logowania</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

// Tester: AccountPage contract (UC-08, sessions, password change) beyond the implementer's tests.

describe("AccountPage (tester)", () => {
  it("nowe hasło równe obecnemu jest blokowane bez żądania", async () => {
    const user = renderPage();
    await user.type(
      await screen.findByLabelText("Obecne hasło"),
      "Kot-w-butach-42",
    );
    await user.type(screen.getByLabelText("Nowe hasło"), "Kot-w-butach-42");
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));
    expect(calls).toHaveLength(0);
  });

  it("zmiana hasła stosuje regułę e-maila zalogowanego użytkownika", async () => {
    const user = renderPage();
    await user.type(
      await screen.findByLabelText("Obecne hasło"),
      "Kot-w-butach-42",
    );
    await screen.findByText("Bezpieczeństwo konta");
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
      await screen.findByLabelText("Potwierdź hasłem"),
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
    await user.click(
      await screen.findByRole("button", {
        name: "Wyloguj ze wszystkich urządzeń",
      }),
    );
    expect(await screen.findByText("Wymagane logowanie")).toBeTruthy();
  });

  it("pusta zgoda hasłem nie usuwa konta", async () => {
    const user = renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Usuń konto na zawsze" }),
    );
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
        await screen.findByLabelText("Potwierdź hasłem"),
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
