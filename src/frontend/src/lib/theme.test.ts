import { renderHook, act, cleanup } from "@testing-library/react";
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

type Listener = (e: { matches: boolean }) => void;

function mockSystem(dark: boolean) {
  const listeners = new Set<Listener>();
  const mql = {
    matches: dark,
    media: "(prefers-color-scheme: dark)",
    addEventListener: (_: string, l: Listener) => listeners.add(l),
    removeEventListener: (_: string, l: Listener) => listeners.delete(l),
    addListener: (l: Listener) => listeners.add(l),
    removeListener: (l: Listener) => listeners.delete(l),
  };
  window.matchMedia = vi.fn().mockReturnValue(mql) as unknown as typeof window.matchMedia;
  return {
    set(next: boolean) {
      mql.matches = next;
      listeners.forEach((l) => l({ matches: next }));
    },
  };
}

async function load() {
  vi.resetModules();
  return await import("./theme");
}

const root = () => document.documentElement;

let store: ReturnType<typeof installStorage>;

beforeEach(() => {
  store = installStorage();
  delete root().dataset.theme;
  root().style.colorScheme = "";
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("getStoredPreference", () => {
  it("defaults to system when nothing is stored", async () => {
    const t = await load();
    expect(t.getStoredPreference()).toBe("system");
  });
  it.each(["light", "dark", "system"])("returns stored %s", async (v) => {
    localStorage.setItem("coffer.theme", v);
    const t = await load();
    expect(t.getStoredPreference()).toBe(v);
  });
  it("falls back to system for an invalid value", async () => {
    localStorage.setItem("coffer.theme", "purple");
    const t = await load();
    expect(t.getStoredPreference()).toBe("system");
  });
  it("falls back to system when getItem throws", async () => {
    vi.spyOn(store, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const t = await load();
    expect(t.getStoredPreference()).toBe("system");
  });
});

describe("resolveTheme / applyTheme", () => {
  it("resolves explicit values regardless of system", async () => {
    mockSystem(true);
    const t = await load();
    expect(t.resolveTheme("light")).toBe("light");
    expect(t.resolveTheme("dark")).toBe("dark");
  });
  it("resolves system via matchMedia", async () => {
    const t = await load();
    mockSystem(true);
    expect(t.resolveTheme("system")).toBe("dark");
    mockSystem(false);
    expect(t.resolveTheme("system")).toBe("light");
    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-color-scheme: dark)");
  });
  it("applyTheme sets data-theme and color-scheme", async () => {
    const t = await load();
    t.applyTheme("dark");
    expect(root().dataset.theme).toBe("dark");
    expect(root().style.colorScheme).toBe("dark");
    t.applyTheme("light");
    expect(root().dataset.theme).toBe("light");
    expect(root().style.colorScheme).toBe("light");
  });
});

describe("setPreference", () => {
  it("default system + dark OS -> dark", async () => {
    mockSystem(true);
    const t = await load();
    t.setPreference(t.getStoredPreference());
    expect(root().dataset.theme).toBe("dark");
  });
  it("stored light wins over dark system", async () => {
    mockSystem(true);
    localStorage.setItem("coffer.theme", "light");
    const t = await load();
    t.setPreference(t.getStoredPreference());
    expect(root().dataset.theme).toBe("light");
  });
  it("persists and applies", async () => {
    mockSystem(false);
    const t = await load();
    t.setPreference("dark");
    expect(localStorage.getItem("coffer.theme")).toBe("dark");
    expect(root().dataset.theme).toBe("dark");
    expect(t.getStoredPreference()).toBe("dark");
  });
  it("still applies the theme when setItem throws", async () => {
    mockSystem(false);
    vi.spyOn(store, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    const t = await load();
    expect(() => t.setPreference("dark")).not.toThrow();
    expect(root().dataset.theme).toBe("dark");
  });
  it("useTheme with system follows live OS changes", async () => {
    const sys = mockSystem(false);
    const t = await load();
    const { result } = renderHook(() => t.useTheme());
    expect(result.current.preference).toBe("system");
    expect(root().dataset.theme).toBe("light");
    act(() => sys.set(true));
    expect(root().dataset.theme).toBe("dark");
    expect(result.current.resolved).toBe("dark");
    act(() => sys.set(false));
    expect(root().dataset.theme).toBe("light");
  });
  it("useTheme with explicit light ignores OS changes", async () => {
    const sys = mockSystem(false);
    const t = await load();
    const { result } = renderHook(() => t.useTheme());
    act(() => result.current.setPreference("light"));
    act(() => sys.set(true));
    expect(root().dataset.theme).toBe("light");
    expect(result.current.resolved).toBe("light");
  });
  it("useTheme setPreference persists and reports resolved", async () => {
    mockSystem(true);
    const t = await load();
    const { result } = renderHook(() => t.useTheme());
    act(() => result.current.setPreference("light"));
    expect(result.current).toMatchObject({ preference: "light", resolved: "light" });
    expect(localStorage.getItem("coffer.theme")).toBe("light");
  });
  it("useTheme: system -> dark detaches OS reaction", async () => {
    const sys = mockSystem(false);
    const t = await load();
    const { result } = renderHook(() => t.useTheme());
    act(() => result.current.setPreference("dark"));
    act(() => sys.set(true));
    act(() => sys.set(false));
    expect(root().dataset.theme).toBe("dark");
    expect(result.current.resolved).toBe("dark");
  });
  it("useTheme removes the matchMedia listener on unmount with the same handler", async () => {
    const added: unknown[] = [];
    const removed: unknown[] = [];
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: (_: string, l: unknown) => added.push(l),
      removeEventListener: (_: string, l: unknown) => removed.push(l),
    }) as unknown as typeof window.matchMedia;
    const t = await load();
    const { unmount } = renderHook(() => t.useTheme());
    expect(added.length).toBeGreaterThan(0);
    unmount();
    for (const h of added) expect(removed).toContain(h);
  });
});
