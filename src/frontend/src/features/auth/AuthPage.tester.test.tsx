import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthPage } from "./AuthPage";

const h = vi.hoisted(() => ({
  handler: null as null | ((req: Request) => Response),
}));
vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
  const req =
    input instanceof Request
      ? input
      : new Request(new URL(String(input), "http://localhost"), init);
  return Promise.resolve(h.handler!(req));
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
const json = (
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

let calls: Request[];
let postResponse: () => Response;

beforeEach(() => {
  calls = [];
  postResponse = () => json({ id: 1, email: "jan@example.com" }, 201);
  h.handler = (req) => {
    if (req.url.endsWith("/api/auth/me"))
      return json({ detail: "Wymagane logowanie" }, 401);
    calls.push(req);
    return postResponse();
  };
});
afterEach(cleanup);

function renderPage(mode: "login" | "register") {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthPage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

// Tester: AuthPage contract (UC-01, UC-09) beyond the implementer's tests.

const fill = async (
  user: ReturnType<typeof renderPage>,
  email: string,
  password: string,
) => {
  await user.type(await screen.findByLabelText("E-mail"), email);
  await user.type(screen.getByLabelText("Hasło"), password);
};

describe("AuthPage (tester)", () => {
  // BUG (medium, accounts/front, queries.ts): openapi-fetch returns error=undefined/'' for an
  // empty error body, and `if (res.error)` treats the 429 as success; fail() is unreachable.
  it(
    "429 bez treści pokazuje polski komunikat zamiast ogólnego błędu",
    async () => {
      postResponse = () =>
        new Response(null, {
          status: 429,
          headers: { "Retry-After": "60", "Content-Length": "0" },
        });
      const user = renderPage("login");
      await fill(user, "jan@example.com", "cokolwiek");
      await user.click(screen.getByRole("button", { name: "Zaloguj" }));
      expect(
        await screen.findByText("Zbyt wiele prób. Spróbuj ponownie później."),
      ).toBeTruthy();
    },
  );

  it("429 przy rejestracji też jest pokazany", async () => {
    postResponse = () =>
      json({ detail: "Zbyt wiele prób. Spróbuj ponownie za 60 min." }, 429, {
        "Retry-After": "3600",
      });
    const user = renderPage("register");
    await fill(user, "jan@example.com", "Kot-w-butach-42");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));
    expect(
      await screen.findByText("Zbyt wiele prób. Spróbuj ponownie za 60 min."),
    ).toBeTruthy();
  });

  it("rejestracja wysyła jedno żądanie register, bez osobnego login", async () => {
    const user = renderPage("register");
    await fill(user, "jan@example.com", "Kot-w-butach-42");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.map((c) => new URL(c.url).pathname)).toEqual([
      "/api/auth/register",
    ]);
  });

  it("zgoda bez dobrego hasła nadal blokuje wysyłkę; 129 znaków też", async () => {
    const user = renderPage("register");
    await fill(user, "jan@example.com", "Ab1-" + "x".repeat(125));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));
    expect(
      screen.getByText("Hasło może mieć najwyżej 128 znaków."),
    ).toBeTruthy();
    expect(calls).toHaveLength(0);
  });

  it("hasło równe części e-maila przed @ jest odrzucane na żywo", async () => {
    const user = renderPage("register");
    await fill(user, "jan.kowalski@example.com", "Jan.Kowalski");
    expect(
      screen.getByText("Hasło nie może być takie samo jak adres e-mail."),
    ).toBeTruthy();
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toMatch(
      /^[01]$/,
    );
  });

  it("409 przy rejestracji pokazuje komunikat serwera", async () => {
    postResponse = () =>
      json({ detail: "Konto z tym adresem e-mail już istnieje" }, 409);
    const user = renderPage("register");
    await fill(user, "jan@example.com", "Kot-w-butach-42");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));
    expect(
      await screen.findByText("Konto z tym adresem e-mail już istnieje"),
    ).toBeTruthy();
  });

  // BUG (low, accounts/front): pydantic 422 for a >128-char login password shows the raw
  // field name ("password: Niepoprawna wartość"); UI messages must be Polish.
  it(
    "422 walidacji przy logowaniu nie pokazuje angielskiej nazwy pola",
    async () => {
      postResponse = () =>
        json(
          {
            detail: [
              {
                type: "string_too_long",
                loc: ["body", "password"],
                msg: "String should have at most 128 characters",
              },
            ],
          },
          422,
        );
      const user = renderPage("login");
      await fill(user, "jan@example.com", "x".repeat(129));
      await user.click(screen.getByRole("button", { name: "Zaloguj" }));
      const alert = await screen.findByText(/Niepoprawna wartość/);
      expect(alert.textContent).not.toMatch(/password/);
    },
  );
});
