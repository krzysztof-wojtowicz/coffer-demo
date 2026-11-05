import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as mod from "./ProfilePage";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ProfilePage: any = (mod as any).ProfilePage ?? (mod as any).default;

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
        return putResponse();
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

  it("zapis wysyła poprawne body i pokazuje sukces", async () => {
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
    await waitFor(() => expect(document.body.textContent).toMatch(/zapisan/i));
  });

  it("wypełnia formularz istniejącym profilem", async () => {
    existing = { horizon: "short", risk: "low", preferred_classes: ["bonds", "deposit"], updated_at: "2026-11-05T10:00:00Z" };
    renderPage();
    await waitFor(() => {
      const checked = (screen.getAllByRole("checkbox") as HTMLInputElement[]).filter((c) => c.checked);
      expect(checked.length).toBe(2);
    });
    expect((screen.getByRole("radio", { name: /krótki/i }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("radio", { name: /niska/i }) as HTMLInputElement).checked).toBe(true);
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
});
