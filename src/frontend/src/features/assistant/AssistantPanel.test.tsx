import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as mod from "./AssistantPanel";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const AssistantPanel: any = (mod as any).AssistantPanel ?? (mod as any).default;

// Stabilny wrapper na fetch (openapi-fetch może przechwycić fetch przy tworzeniu klienta).
type Handler = (req: Request) => Promise<Response> | Response;
const h = vi.hoisted(() => ({ handler: null as null | ((req: Request) => unknown) }));
// undici's Request rejects jsdom's AbortSignal ("Expected signal to be an instance of
// AbortSignal"), so the signal is stripped before `new Request`, exposed again as
// `req.signal` for assertions, and honoured by rejecting with AbortError on abort.
vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
  if (input instanceof Request) return Promise.resolve(h.handler!(input));
  const { signal, ...rest } = init ?? {};
  const req = new Request(new URL(String(input), "http://localhost"), rest);
  if (!signal) return Promise.resolve(h.handler!(req));
  Object.defineProperty(req, "signal", { value: signal });
  const abortError = () => new DOMException("The operation was aborted.", "AbortError");
  if (signal.aborted) return Promise.reject(abortError());
  return new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(abortError()), { once: true });
    Promise.resolve(h.handler!(req)).then(resolve, reject);
  });
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const summary = (over = {}) => ({
  month: "2026-10", income: "5000.00", expenses: "3000.00", balance: "2000.00", surplus: "2000.00",
  by_category: [
    { category_id: 1, category_name: "Jedzenie", expenses: "1234.56" },
    { category_id: 2, category_name: "Transport", expenses: "321.00" },
  ],
  ...over,
});
const suggestion = {
  summary: "Odłóż większość nadwyżki na poduszkę finansową.",
  id: 5, type: "surplus", month: "2026-10", profile_used: true,
  rationale: [
    { claim: "Brak poduszki bezpieczeństwa", refers_to: "budget", value: "2000,00 zł" },
    { claim: "Niska tolerancja ryzyka", refers_to: "profile", value: "niska" },
  ],
  risks: ["Inflacja zmniejsza wartość oszczędności"],
  disclaimer: "To tylko sugestia, nie porada finansowa.",
  model: "qwen3:8b", generated_at: "2026-11-05T10:00:00Z", duration_ms: 12340,
};

const enc = new TextEncoder();
const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const sseResponse = (chunks: string[]) =>
  new Response(
    new ReadableStream({
      start(c) {
        for (const ch of chunks) c.enqueue(enc.encode(ch));
        c.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
const result = (over: Record<string, unknown> = {}) =>
  sse("result", { summary: summary(), ai_status: "ok", suggestion, run_id: 42, ...over });
const okStream = (over: Record<string, unknown> = {}) =>
  sseResponse([
    sse("status", { message: "Liczę podsumowanie miesiąca…" }),
    sse("summary", summary()),
    result(over),
  ]);

let surplusCalls: Request[];
function route(surplus: Handler, status: unknown = { provider: "ollama", model: "qwen3:8b", available: true }) {
  surplusCalls = [];
  h.handler = (req) => {
    if (req.url.includes("/api/agent/status")) return json(status);
    if (req.url.includes("/api/agent/surplus")) {
      surplusCalls.push(req);
      return surplus(req);
    }
    return json({}, 404);
  };
}

function renderPanel(sum = summary(), month = "2026-10") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const user = userEvent.setup();
  const ui = (m: string, s: unknown) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AssistantPanel month={m} summary={s} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  const r = render(ui(month, sum));
  return { user, rerender: (m: string, s = sum) => r.rerender(ui(m, s)) };
}

const btn = () => screen.queryByRole("button", { name: "Zaproponuj, jak wykorzystać nadwyżkę" }) as HTMLButtonElement | null;
const text = () => document.body.textContent ?? "";

beforeEach(() => route(() => okStream()));
afterEach(cleanup);

describe("AssistantPanel", () => {
  it("idle: tytuł, opis, przycisk aktywny", async () => {
    renderPanel();
    expect(text()).toContain("Asystent AI");
    expect(text()).toContain("Asystent przeanalizuje podsumowanie miesiąca");
    expect(btn()!.disabled).toBe(false);
    await waitFor(() => expect(text()).toContain("qwen3:8b · dostępny"));
  });

  it("status: model niedostępny, przycisk nadal aktywny", async () => {
    route(() => json({}), { provider: "ollama", model: "qwen3:8b", available: false });
    renderPanel();
    await waitFor(() => expect(text()).toContain("Model niedostępny"));
    expect(btn()!.disabled).toBe(false);
  });

  it("status: AI wyłączone przy provider none", async () => {
    route(() => json({}), { provider: "none", model: null, available: false });
    renderPanel();
    await waitFor(() => expect(text()).toContain("AI wyłączone"));
  });

  it("sekcja danych zawiera kwoty z summary i zapewnienie o prywatności", async () => {
    renderPanel();
    const details = document.querySelector("details")!;
    expect(details.textContent).toContain("Jakie dane trafiają do modelu?");
    for (const v of ["5000", "3000", "2000", "Jedzenie", "1234", "Transport", "321"]) {
      expect(details.textContent).toContain(v);
    }
    expect(details.textContent).toContain("Nie wysyłamy opisów transakcji, e-maila ani innych danych osobowych.");
    await waitFor(() => expect(details.textContent).toContain("Model działa lokalnie (Ollama)."));
  });

  it("prywatność: dostawca chmurowy z /api/agent/status", async () => {
    route(() => json({}), { provider: "gemini", model: "gemini-3.8-flash", available: true });
    renderPanel();
    const details = document.querySelector("details")!;
    await waitFor(() =>
      expect(details.textContent).toContain(
        "Model działa w chmurze (Google Gemini); wysyłamy tylko zagregowane dane.",
      ),
    );
    expect(details.textContent).not.toContain("lokalnie");
  });

  it("prywatność: bez znanego dostawcy brak deklaracji o miejscu działania modelu", async () => {
    route(() => json({}), {}); // nieczytelny status -> brak dostawcy
    renderPanel();
    const details = document.querySelector("details")!;
    await new Promise((r) => setTimeout(r, 20));
    expect(details.textContent).toContain("Nie wysyłamy opisów transakcji");
    expect(details.textContent).not.toContain("lokalnie");
    expect(details.textContent).not.toContain("w chmurze");
  });

  it("surplus 0.00: przycisk wyłączony, wyjaśnienie, brak wywołania API", async () => {
    const { user } = renderPanel(summary({ surplus: "0.00" }));
    expect(text()).toContain("W tym miesiącu nie ma nadwyżki, więc nie ma czego rozdysponować.");
    expect(btn()!.disabled).toBe(true);
    await user.click(btn()!);
    expect(surplusCalls.length).toBe(0);
  });

  it("klik: stan ładowania z tekstami i Anuluj, wysyła miesiąc", async () => {
    route(() => new Promise<Response>(() => {}));
    const { user } = renderPanel();
    await user.click(btn()!);
    await waitFor(() => expect(text()).toContain("Asystent analizuje dane…"));
    expect(text()).toContain("10–30 s");
    expect(text()).toMatch(/\d+ s/);
    expect(screen.getByRole("button", { name: "Anuluj" })).toBeTruthy();
    await waitFor(() => expect(surplusCalls.length).toBe(1));
    expect(await surplusCalls[0].json()).toEqual({ month: "2026-10" });
  });

  it("Anuluj wraca do idle", async () => {
    route(() => new Promise<Response>(() => {}));
    const { user } = renderPanel();
    await user.click(btn()!);
    await user.click(await screen.findByRole("button", { name: "Anuluj" }));
    await waitFor(() => expect(btn()).not.toBeNull());
    expect(text()).not.toContain("Asystent analizuje dane…");
  });

  it("ok: summary, rationale, disclaimer, stopka i przyciski", async () => {
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
    expect(text()).toContain("Dlaczego:");
    for (const r of suggestion.rationale) expect(text()).toContain(r.claim);
    expect(text()).toContain(suggestion.disclaimer);
    expect(text()).toContain("qwen3:8b");
    expect(text()).toMatch(/12[,.]3 s/);
    expect(screen.getByRole("button", { name: "Wygeneruj ponownie" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wyczyść" })).toBeTruthy();
  });

  it("wysyła POST na /surplus/stream", async () => {
    const { user } = renderPanel();
    await user.click(btn()!);
    await waitFor(() => expect(surplusCalls.length).toBe(1));
    expect(surplusCalls[0].method).toBe("POST");
    expect(surplusCalls[0].url).toContain("/api/agent/surplus/stream");
  });

  it("kroki statusu pojawiają się w kolejności i po wyniku znikają", async () => {
    let ctl!: ReadableStreamDefaultController<Uint8Array>;
    route(() =>
      new Response(new ReadableStream({ start: (c) => { ctl = c; } }), {
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const { user } = renderPanel();
    await user.click(btn()!);
    await waitFor(() => expect(surplusCalls.length).toBe(1));
    await waitFor(() => expect(ctl).toBeTruthy());
    ctl.enqueue(enc.encode(sse("status", { message: "Liczę podsumowanie miesiąca…" })));
    await waitFor(() => expect(text()).toContain("Liczę podsumowanie miesiąca…"));
    ctl.enqueue(enc.encode(sse("summary", summary())));
    ctl.enqueue(enc.encode(sse("status", { message: "Sprawdzam profil inwestycyjny…" })));
    await waitFor(() => expect(text()).toContain("Sprawdzam profil inwestycyjny…"));
    expect(text().indexOf("Liczę podsumowanie")).toBeLessThan(text().indexOf("Sprawdzam profil"));
    expect(text()).toContain("✓");
    expect(text()).toMatch(/\d+ s/);
    ctl.enqueue(enc.encode(result()));
    ctl.close();
    await screen.findByText(suggestion.summary);
  });

  it("zdarzenie rozcięte między kawałkami strumienia jest składane", async () => {
    const full = result();
    route(() => sseResponse([sse("status", { message: "Krok A" }), full.slice(0, 30), full.slice(30, 90), full.slice(90)]));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
  });

  it("ok: claim, etykiety źródeł, value, ryzyka, stopka, link do śladu", async () => {
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
    for (const r of suggestion.rationale) {
      expect(text()).toContain(r.claim);
      expect(text()).toContain(r.value);
    }
    expect(text()).toContain("Budżet");
    expect(text()).toContain("Profil");
    expect(text()).toContain("Ryzyka:");
    expect(text()).toContain(suggestion.risks[0]);
    expect(text()).toContain("z profilem");
    const link = screen.getByRole("link", { name: /Pokaż ślad agenta/ });
    expect(link.getAttribute("href")).toBe("/assistant/runs/42");
    expect(text()).not.toContain("Uzupełnij profil inwestycyjny");
  });

  it("Portfel jako etykieta źródła", async () => {
    const s2 = { ...suggestion, rationale: [{ claim: "Portfel jest skoncentrowany", refers_to: "portfolio", value: "80%" }] };
    route(() => okStream({ suggestion: s2 }));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(s2.summary);
    expect(text()).toContain("Portfel");
    expect(text()).toContain("80%");
  });

  it("brak ryzyk: sekcja Ryzyka nie jest pokazana", async () => {
    route(() => okStream({ suggestion: { ...suggestion, risks: [] } }));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
    expect(text()).not.toContain("Ryzyka:");
  });

  it("profile_used=false: zachęta i link do /profile, stopka bez profilu", async () => {
    route(() => okStream({ suggestion: { ...suggestion, profile_used: false } }));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
    expect(text()).toContain("Uzupełnij profil inwestycyjny, aby sugestie były lepiej dopasowane");
    expect(text()).toContain("bez profilu");
    const links = screen.getAllByRole("link");
    expect(links.some((l) => l.getAttribute("href") === "/profile")).toBe(true);
  });

  it("limited: komunikat o dziennym limicie", async () => {
    route(() => sseResponse([result({ ai_status: "limited", suggestion: null, run_id: null })]));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/Osiągnięto dzienny limit zapytań do asystenta\. Spróbuj jutro\./);
    expect(text()).not.toContain("chwilowo niedostępny");
  });

  it("strumień zamknięty bez result -> unavailable", async () => {
    route(() => sseResponse([sse("status", { message: "Krok A" })]));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/Asystent AI jest chwilowo niedostępny/);
  });

  it("Wyczyść wraca do idle", async () => {
    const { user } = renderPanel();
    await user.click(btn()!);
    await user.click(await screen.findByRole("button", { name: "Wyczyść" }));
    await waitFor(() => expect(btn()).not.toBeNull());
    expect(text()).not.toContain(suggestion.summary);
  });

  it("Wygeneruj ponownie woła API drugi raz", async () => {
    const { user } = renderPanel();
    await user.click(btn()!);
    await user.click(await screen.findByRole("button", { name: "Wygeneruj ponownie" }));
    await waitFor(() => expect(surplusCalls.length).toBe(2));
  });

  it("unavailable z API: komunikat i Spróbuj ponownie", async () => {
    route(() => sseResponse([result({ ai_status: "unavailable", suggestion: null, run_id: null })]));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/Asystent AI jest chwilowo niedostępny\. Wyliczenia powyżej są aktualne\./);
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeTruthy();
  });

  it("błąd HTTP 500 -> ten sam stan unavailable", async () => {
    route(() => json({ detail: "boom" }, 500));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/Asystent AI jest chwilowo niedostępny/);
  });

  it("błąd sieci -> stan unavailable", async () => {
    route(() => Promise.reject(new TypeError("network")));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/Asystent AI jest chwilowo niedostępny/);
  });

  it("no_surplus z API: wyjaśnienie o braku nadwyżki", async () => {
    route(() => sseResponse([result({ ai_status: "no_surplus", suggestion: null, run_id: null })]));
    const { user } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(/W tym miesiącu nie ma nadwyżki/);
  });

  it("zmiana month resetuje panel do idle", async () => {
    const { user, rerender } = renderPanel();
    await user.click(btn()!);
    await screen.findByText(suggestion.summary);
    rerender("2026-09", summary({ month: "2026-09" }));
    await waitFor(() => expect(btn()).not.toBeNull());
    expect(text()).not.toContain(suggestion.summary);
  });

  it("zmiana month w trakcie ładowania przerywa żądanie", async () => {
    let signal: AbortSignal | undefined;
    route((req) => {
      signal = req.signal;
      return new Promise<Response>(() => {});
    });
    const { user, rerender } = renderPanel();
    await user.click(btn()!);
    await waitFor(() => expect(surplusCalls.length).toBe(1));
    rerender("2026-09", summary({ month: "2026-09" }));
    await waitFor(() => expect(btn()).not.toBeNull());
    expect(text()).not.toContain("Asystent analizuje dane…");
    expect(signal?.aborted).toBe(true);
  });
});
