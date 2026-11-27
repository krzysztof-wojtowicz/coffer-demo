import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function installStorage() {
  const data = new Map<string, string>();
  const fake = {
    getItem: vi.fn((k: string) => (data.has(k) ? data.get(k)! : null)),
    setItem: vi.fn((k: string, v: string) => void data.set(k, String(v))),
    removeItem: vi.fn((k: string) => void data.delete(k)),
    clear: vi.fn(() => data.clear()),
    key: () => null,
    length: 0,
  };
  vi.stubGlobal("localStorage", fake);
  Object.defineProperty(window, "localStorage", { value: fake, configurable: true });
  return fake;
}

// Module state (session preference) must not leak between tests: reload per test.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let ThemeToggle: any;

function mockSystem(dark: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: dark,
    media: "(prefers-color-scheme: dark)",
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  }) as unknown as typeof window.matchMedia;
}

let store: ReturnType<typeof installStorage>;

beforeEach(async () => {
  vi.resetModules();
  const mod = await import("./ThemeToggle");
  ThemeToggle = mod.ThemeToggle;
  store = installStorage();
  delete document.documentElement.dataset.theme;
  mockSystem(false);
});
afterEach(cleanup);

const radio = (name: string) => screen.getByRole("radio", { name });
const checked = () =>
  screen.getAllByRole("radio").filter((r) => r.getAttribute("aria-checked") === "true");

describe("ThemeToggle", () => {
  it("exposes a radiogroup with three labelled radios", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("radiogroup")).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    for (const n of ["Jasny", "Ciemny", "Systemowy"]) expect(radio(n)).toBeTruthy();
  });

  it("selects Systemowy by default with exactly one checked", () => {
    render(<ThemeToggle />);
    expect(checked()).toHaveLength(1);
    expect(radio("Systemowy").getAttribute("aria-checked")).toBe("true");
  });

  it("reflects stored preference", () => {
    localStorage.setItem("coffer.theme", "dark");
    render(<ThemeToggle />);
    expect(radio("Ciemny").getAttribute("aria-checked")).toBe("true");
  });

  it("click changes theme, checked state and storage", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(radio("Ciemny"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("coffer.theme")).toBe("dark");
    expect(radio("Ciemny").getAttribute("aria-checked")).toBe("true");
    expect(radio("Systemowy").getAttribute("aria-checked")).toBe("false");
    await user.click(radio("Jasny"));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("coffer.theme")).toBe("light");
  });

  it("system choice with dark OS resolves to dark", async () => {
    mockSystem(true);
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(radio("Jasny"));
    await user.click(radio("Systemowy"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("coffer.theme")).toBe("system");
  });

  it("arrow keys change the selection", async () => {
    const user = userEvent.setup();
    localStorage.setItem("coffer.theme", "light");
    render(<ThemeToggle />);
    radio("Jasny").focus();
    await user.keyboard("{ArrowRight}");
    expect(checked()).toHaveLength(1);
    expect(radio("Jasny").getAttribute("aria-checked")).toBe("false");
    const after = localStorage.getItem("coffer.theme");
    expect(after).not.toBe("light");
    await user.keyboard("{ArrowLeft}");
    expect(localStorage.getItem("coffer.theme")).toBe("light");
    expect(radio("Jasny").getAttribute("aria-checked")).toBe("true");
  });

  it("persists across remount", async () => {
    const user = userEvent.setup();
    const first = render(<ThemeToggle />);
    await user.click(radio("Ciemny"));
    first.unmount();
    delete document.documentElement.dataset.theme;
    render(<ThemeToggle />);
    expect(radio("Ciemny").getAttribute("aria-checked")).toBe("true");
  });

  function breakStorage() {
    vi.spyOn(store, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(store, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
  }

  it("works when localStorage throws: choice is kept in session", async () => {
    breakStorage();
    const user = userEvent.setup();
    render(<ThemeToggle />);
    expect(radio("Systemowy").getAttribute("aria-checked")).toBe("true");
    await user.click(radio("Ciemny"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(radio("Ciemny").getAttribute("aria-checked")).toBe("true");
    expect(checked()).toHaveLength(1);
  });

  it("broken storage: selection survives an OS change", async () => {
    const listeners = new Set<() => void>();
    const mql = {
      matches: false,
      addEventListener: (_: string, l: () => void) => listeners.add(l),
      removeEventListener: (_: string, l: () => void) => listeners.delete(l),
    };
    window.matchMedia = vi.fn().mockReturnValue(mql) as unknown as typeof window.matchMedia;
    breakStorage();
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(radio("Ciemny"));
    mql.matches = true;
    act(() => listeners.forEach((l) => l()));
    expect(radio("Ciemny").getAttribute("aria-checked")).toBe("true");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("broken storage: two instances stay in sync", async () => {
    breakStorage();
    const user = userEvent.setup();
    render(
      <>
        <div data-testid="a"><ThemeToggle /></div>
        <div data-testid="b"><ThemeToggle /></div>
      </>,
    );
    const a = within(screen.getByTestId("a"));
    const b = within(screen.getByTestId("b"));
    await user.click(a.getByRole("radio", { name: "Ciemny" }));
    expect(a.getByRole("radio", { name: "Ciemny" }).getAttribute("aria-checked")).toBe("true");
    expect(b.getByRole("radio", { name: "Ciemny" }).getAttribute("aria-checked")).toBe("true");
    expect(b.getByRole("radio", { name: "Systemowy" }).getAttribute("aria-checked")).toBe("false");
  });
});
