import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
const target = [{ asset_class: "etf", share_pct: 60 }, { asset_class: "bond", share_pct: 40 }];
const out = { horizon: "medium", risk: "medium", preferred_classes: ["etf", "bond"], target, updated_at: "2026-11-05T10:00:00Z" };
const saved = (o: object) => ({ horizon: "short", risk: "low", preferred_classes: ["bond"], target, updated_at: "2026-11-05T10:00:00Z", ...o });

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
  it("formularz: przyciski horyzontu i ryzyka oraz 7 klas aktywów", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    const horizon = within(screen.getByRole("group", { name: "Horyzont inwestycyjny" }));
    expect(horizon.getAllByRole("button").length).toBe(3);
    expect(within(screen.getByRole("group", { name: "Tolerancja ryzyka" })).getAllByRole("button").length).toBe(3);
    expect(within(screen.getByRole("group", { name: "Preferowane klasy aktywów" })).getAllByRole("button").length).toBe(7);
  });

  it("przycisk zablokowany bez zaznaczonej klasy", async () => {
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    expect(save().disabled).toBe(true);
    await user.click(screen.getByRole("button", { name: "Akcje" }));
    expect(save().disabled).toBe(false);
    await user.click(screen.getByRole("button", { name: "Akcje" }));
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
    await user.click(screen.getByRole("button", { name: /długi/i }));
    await user.click(screen.getByRole("button", { name: "Wysoka" }));
    await user.click(screen.getByRole("button", { name: "Gotówka i lokaty" }));
    await user.click(screen.getByRole("button", { name: "Akcje" }));
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    const body = await puts[0].json();
    expect(body.horizon).toBe("long");
    expect(body.risk).toBe("high");
    expect([...body.preferred_classes].sort()).toEqual(["cash", "stock"]);
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(screen.getByRole("status").textContent).toMatch(/zapisan/i);
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
  });

  it("istniejący profil: widok z horyzontem, ryzykiem i wykresem docelowej alokacji", async () => {
    existing = saved({ horizon: "long", risk: "high", preferred_classes: ["stock", "etf"] });
    renderPage();
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
    const text = document.body.textContent ?? "";
    expect(text).toContain("Długi (powyżej 5 lat)");
    expect(text).toContain("Wysoka");
    expect(text).toContain("Docelowa alokacja");
    expect(text).toContain("60%");
    expect(text).toContain("ETF");
    expect(text).toContain("Obligacje");
    expect(text).toContain("nie stanowi porady");
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("ETF");
  });

  it("Zmień profil otwiera wypełniony formularz, Anuluj wraca bez zapisu", async () => {
    existing = saved({ preferred_classes: ["bond", "cash"] });
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    const pressed = (n: string | RegExp) => screen.getByRole("button", { name: n }).getAttribute("aria-pressed");
    expect(pressed(/krótki/i)).toBe("true");
    expect(pressed("Niska")).toBe("true");
    expect(pressed("Obligacje")).toBe("true");
    expect(pressed("Gotówka i lokaty")).toBe("true");
    expect(pressed("Akcje")).toBe("false");
    await user.click(screen.getByRole("button", { name: "Wysoka" }));
    await user.click(screen.getByRole("button", { name: "Anuluj" }));
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(puts.length).toBe(0);
    expect(document.body.textContent).toContain("Niska");
  });

  it("edycja istniejącego profilu zapisuje i wraca do podsumowania", async () => {
    existing = saved({});
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    await user.click(screen.getByRole("button", { name: "Średnia" }));
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    expect((await puts[0].json()).risk).toBe("medium");
    await screen.findByRole("button", { name: "Zmień profil" });
  });

  it("błąd 422 pokazuje komunikat po polsku", async () => {
    putResponse = () => json({ detail: "Klasy aktywów nie mogą się powtarzać" }, 422);
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getByRole("button", { name: "Akcje" }));
    await user.click(save());
    await waitFor(() => expect(puts.length).toBe(1));
    await waitFor(() => expect(document.body.textContent).toContain("Klasy aktywów nie mogą się powtarzać"));
  });

  it("błąd wczytania profilu pokazuje komunikat zamiast formularza", async () => {
    h.handler = () => json({ detail: "boom" }, 500);
    renderPage();
    await waitFor(() => expect(document.body.textContent).toContain("Nie udało się wczytać profilu."));
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
  });

  it("błąd 500 bez JSON przy zapisie: ogólny komunikat, formularz zostaje", async () => {
    putResponse = () => new Response("Internal Server Error", { status: 500 });
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getByRole("button", { name: "Akcje" }));
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Nie udało się zapisać profilu."));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("button", { name: "Zapisz profil" })).toBeTruthy();
  });

  it("422 z listą błędów walidacji (format FastAPI) pokazuje każdy msg", async () => {
    putResponse = () =>
      json({ detail: [{ loc: ["body", "risk"], msg: "Błąd A" }, { loc: ["body", "horizon"], msg: "Błąd B" }] }, 422);
    const user = renderPage();
    await screen.findByRole("button", { name: "Zapisz profil" });
    await user.click(screen.getByRole("button", { name: "Akcje" }));
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Błąd A"));
    expect(document.body.textContent).toContain("Błąd B");
  });

  it("błąd zapisu w trybie edycji: zostaje formularz, Anuluj wraca do starego profilu", async () => {
    existing = saved({});
    putResponse = () => json({ detail: "Serwer odrzucił zmianę" }, 400);
    const user = renderPage();
    await user.click(await screen.findByRole("button", { name: "Zmień profil" }));
    await user.click(screen.getByRole("button", { name: "Wysoka" }));
    await user.click(save());
    await waitFor(() => expect(document.body.textContent).toContain("Serwer odrzucił zmianę"));
    await user.click(screen.getByRole("button", { name: "Anuluj" }));
    await screen.findByRole("button", { name: "Zmień profil" });
    expect(document.body.textContent).toContain("Niska");
    expect(screen.queryByRole("status")).toBeNull();
  });
});
