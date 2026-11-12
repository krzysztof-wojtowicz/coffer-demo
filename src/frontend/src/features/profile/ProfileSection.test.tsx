import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as mod from "./ProfileSection";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ProfilePage: any = (mod as any).ProfileSection ?? (mod as any).default;

const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => unknown) }));
vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
  const req = input instanceof Request ? input : new Request(new URL(String(input), "http://localhost"), init);
  return Promise.resolve(h.handler!(req));
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let puts: Request[];
let existing: unknown = null;
let putResponse: () => Response;
const out = { horizon: "medium", risk: "medium", preferred_classes: ["etf"], updated_at: "2026-11-05T10:00:00Z" };

beforeEach(() => {
  puts = [];
  existing = null;
  putResponse = () => json(out);
  h.handler = (req) => {
    if (req.url.includes("/api/profile")) {
      if (req.method === "PUT") {
        puts.push(req);
        const res = putResponse();
        if (res.ok) existing = out;
        return res;
      }
      return json(existing);
    }
    return json({}, 404);
  };
});
afterEach(cleanup);

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return user;
}
const save = () => screen.getByRole("button", { name: "Zapisz profil" }) as HTMLButtonElement;

describe("ProfilePage", () => {
  it("renderuje opcje horyzontu, ryzyka i 7 klas aktywów", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    expect(screen.getAllByRole("radio").length).toBe(6);
    expect(screen.getAllByRole("checkbox").length).toBe(7);
    expect(document.body.textContent).toContain("nie zmienia");
  });

  it("przycisk zablokowany bez zaznaczonej klasy", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    for (const c of screen.getAllByRole("checkbox") as HTMLInputElement[]) expect(c.checked).toBe(false);
    expect(save().disabled).toBe(true);
    const user = userEvent.setup();
    await user.click(screen.getAllByRole("checkbox")[0]);
    expect(save().disabled).toBe(false);
    await user.click(screen.getAllByRole("checkbox")[0]);
    expect(save().disabled).toBe(true);
  });

  it("pusty stan pokazuje zachętę i formularz bez przycisku Anuluj", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    expect(document.body.textContent).toContain("Nie masz jeszcze profilu");
    expect(screen.queryByRole("button", { name: "Anuluj" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Zmień profil" })).toBeNull();
  });

  it("zapis wysyła poprawne body i wraca do podsumowania z komunikatem sukcesu", async () => {
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getByRole("radio", { name: /długi/i }));
    await user.click(screen.getByRole("radio", { name: /wysoka/i }));
    // zaznacz 1. i 3. checkbox; kolejność klas: cash, deposit, stocks, ...
    const boxes = screen.getAllByRole("checkbox");
    await user.click(boxes[0]);
    await user.click(boxes[2]);
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    const body = await puts[0].json();
    expect(body.horizon).toBe("long");
    expect(body.risk).toBe("high");
    expect([...body.preferred_classes].sort()).toEqual(["cash", "stocks"]);
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(screen.getByRole("status").textContent).toMatch(/zapisan/i);
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
  });

  it("istniejący profil: domyślnie widok podsumowania zamiast formularza", async () => {
    existing = { horizon: "long", risk: "high", preferred_classes: ["stocks", "etf"], updated_at: "2026-11-05T10:00:00Z" };
    renderPage();
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
    expect(screen.queryAllByRole("radio").length).toBe(0);
    const text = document.body.textContent ?? "";
    expect(text).toContain("Dynamiczny");
    expect(text).toContain("Długi (powyżej 5 lat)");
    expect(text).toContain("Fundusze ETF");
    expect(text).not.toContain("Lokaty");
    expect(text).toContain("5 listopada 2026");
    expect(text).toContain("Orientacyjna alokacja");
    expect(text).toMatch(/ilustracj/i);
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("3");
    expect(screen.getByRole("link", { name: "Zobacz Portfel" }).getAttribute("href")).toBe("/portfolio");
  });

  it("Zmień profil otwiera wypełniony formularz, Anuluj wraca bez zapisu", async () => {
    existing = { horizon: "short", risk: "low", preferred_classes: ["bonds", "deposit"], updated_at: "2026-11-05T10:00:00Z" };
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    const checked = (screen.getAllByRole("checkbox") as HTMLInputElement[]).filter((c) => c.checked);
    expect(checked.length).toBe(2);
    expect((screen.getByRole("radio", { name: /krótki/i }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("radio", { name: /niska/i }) as HTMLInputElement).checked).toBe(true);
    await user.click(screen.getByRole("radio", { name: /wysoka/i }));
    await user.click(screen.getByRole("button", { name: "Anuluj" }));
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(puts.length).toBe(0);
    expect(document.body.textContent).toContain("Ostrożny");
  });

  it("edycja istniejącego profilu zapisuje i wraca do podsumowania", async () => {
    existing = { horizon: "short", risk: "low", preferred_classes: ["bonds"], updated_at: "2026-11-05T10:00:00Z" };
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    await user.click(screen.getByRole("radio", { name: /średnia/i }));
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    expect((await puts[0].json()).risk).toBe("medium");
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(document.body.textContent).toContain("Umiarkowany");
  });

  it("błąd 422 pokazuje komunikat po polsku", async () => {
    putResponse = () => json({ detail: "Klasy aktywów nie mogą się powtarzać" }, 422);
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    await waitFor(() => expect(document.body.textContent).toContain("Klasy aktywów nie mogą się powtarzać"));
  });

  // --- przypadki brzegowe (tester) ---

  it("błąd wczytania profilu pokazuje komunikat zamiast formularza", async () => {
    h.handler = () => json({ detail: "boom" }, 500);
    renderPage();
    await waitFor(() => expect(document.body.textContent).toContain("Nie udało się wczytać profilu."));
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Zmień profil" })).toBeNull();
  });

  it("błąd 500 bez JSON przy zapisie: ogólny komunikat, brak sukcesu, formularz zostaje", async () => {
    putResponse = () => new Response("Internal Server Error", { status: 500 });
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Nie udało się zapisać profilu."));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("button", { name: "Zapisz profil" })).toBeTruthy();
    expect(document.body.textContent).toContain("Nie masz jeszcze profilu");
  });

  it("błąd sieci przy zapisie pokazuje ogólny komunikat", async () => {
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    const prev = h.handler!;
    h.handler = (req) => (req.method === "PUT" ? Promise.reject(new TypeError("Failed to fetch")) : prev(req));
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Nie udało się zapisać profilu."));
  });

  it("422 z listą błędów walidacji (format FastAPI) pokazuje każdy msg", async () => {
    putResponse = () =>
      json({ detail: [{ loc: ["body", "risk"], msg: "Błąd A" }, { loc: ["body", "horizon"], msg: "Błąd B" }] }, 422);
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Błąd A"));
    expect(document.body.textContent).toContain("Błąd B");
  });

  it("błąd zapisu w trybie edycji: zostaje formularz, Anuluj wraca do starego profilu", async () => {
    existing = { horizon: "short", risk: "low", preferred_classes: ["bonds"], updated_at: "2026-11-05T10:00:00Z" };
    putResponse = () => json({ detail: "Serwer odrzucił zmianę" }, 400);
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    await user.click(screen.getByRole("radio", { name: /wysoka/i }));
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Serwer odrzucił zmianę"));
    expect(screen.getByRole("button", { name: "Zapisz profil" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Anuluj" }));
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(document.body.textContent).toContain("Ostrożny");
    expect(document.body.textContent).not.toContain("Dynamiczny");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("komunikat sukcesu znika po ponownym wejściu w edycję", async () => {
    existing = { horizon: "short", risk: "low", preferred_classes: ["bonds"], updated_at: "2026-11-05T10:00:00Z" };
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    await user.click(save());
    await screen.findByRole("status");
    await user.click(screen.getByRole("button", { name: "Zmień profil" }));
    expect(screen.queryByRole("status")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Anuluj" }));
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(screen.queryByRole("status")).toBeNull();
  });
});
