import html from "../index.html?raw";
import initJs from "../public/theme-init.js?raw";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)].map((m) => ({
  attrs: m[1],
  body: m[2],
}));

// Returns the init script source when index.html references it (only public/theme-init.js is known).
function initScriptSource(): string | null {
  const s = scripts.find((x) => /src=/.test(x.attrs) && !/type=["']module["']/.test(x.attrs));
  const src = s?.attrs.match(/src=["']([^"']+)["']/)?.[1];
  return src === "/theme-init.js" ? initJs : null;
}

function mockSystem(dark: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: dark,
    media: "(prefers-color-scheme: dark)",
    addEventListener: () => {},
    removeEventListener: () => {},
  }) as unknown as typeof window.matchMedia;
}

function runInit() {
  new Function(initScriptSource()!)();
}

let store: ReturnType<typeof installStorage>;

beforeEach(() => {
  store = installStorage();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
  vi.restoreAllMocks();
});

describe("index.html CSP compliance", () => {
  it("has no inline script with code", () => {
    for (const s of scripts) expect(s.body.trim()).toBe("");
  });
  it("loads a classic (non-module) external init script in <head> before the app", () => {
    const head = html.split("</head>")[0];
    expect(/<script\b(?![^>]*type=["']module["'])[^>]*\bsrc=/i.test(head)).toBe(true);
    expect(initScriptSource()).toBeTruthy();
  });
});

describe("startup theme script", () => {
  it("no stored value + dark system -> dark", () => {
    mockSystem(true);
    runInit();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });
  it("no stored value + light system -> light", () => {
    mockSystem(false);
    runInit();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
  it("stored light wins over dark system", () => {
    mockSystem(true);
    localStorage.setItem("coffer.theme", "light");
    runInit();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
  it("stored dark wins over light system", () => {
    mockSystem(false);
    localStorage.setItem("coffer.theme", "dark");
    runInit();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
  it("stored system follows OS; invalid value follows OS", () => {
    mockSystem(true);
    localStorage.setItem("coffer.theme", "system");
    runInit();
    expect(document.documentElement.dataset.theme).toBe("dark");
    delete document.documentElement.dataset.theme;
    localStorage.setItem("coffer.theme", "bogus");
    runInit();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
  // BUG: init script wraps everything in one try/catch, so a throwing getItem leaves data-theme unset.
  it("does not throw and falls back to system when getItem throws", () => {
    mockSystem(true);
    vi.spyOn(store, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(() => runInit()).not.toThrow();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
