import css from "./index.css?raw";
import badgeSrc from "./components/ui/Badge.tsx?raw";
import toggleSrc from "./components/ThemeToggle.tsx?raw";
import profileSrc from "./features/profile/ProfilePage.tsx?raw";
import { describe, expect, it } from "vitest";


function block(startRe: RegExp): string {
  const m = startRe.exec(css);
  if (!m) throw new Error(`block not found: ${startRe}`);
  let i = css.indexOf("{", m.index) + 1;
  const start = i;
  let depth = 1;
  while (depth > 0 && i < css.length) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") depth--;
    i++;
  }
  return css.slice(start, i - 1);
}

function tokens(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--color-([\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

type RGBA = [number, number, number, number];

function parse(v: string): RGBA {
  const hex = /^#([0-9a-f]{3,8})$/i.exec(v);
  if (hex) {
    let h = hex[1];
    if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join("");
    const n = (i: number) => parseInt(h.slice(i, i + 2), 16);
    return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
  }
  const rgb = /^rgba?\(\s*([^)]+)\)$/i.exec(v);
  if (rgb) {
    const [colors, alpha] = rgb[1].split("/").map((s) => s.trim());
    const parts = colors.split(/[\s,]+/).filter(Boolean);
    let a = alpha ?? (parts.length === 4 ? parts[3] : "1");
    const [r, g, b] = parts.slice(0, 3).map(Number);
    const af = a.endsWith("%") ? parseFloat(a) / 100 : parseFloat(a);
    return [r, g, b, af];
  }
  throw new Error(`unsupported color: ${v}`);
}

function over(fg: RGBA, bg: RGBA): RGBA {
  const a = fg[3];
  return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)).concat(1) as RGBA;
}

function lum([r, g, b]: RGBA): number {
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function ratio(fgV: string, bgV: string, base?: RGBA): number {
  const bg0 = parse(bgV);
  const bg = bg0[3] < 1 ? over(bg0, base ?? [0, 0, 0, 1]) : bg0;
  const fg = over(parse(fgV), bg);
  const [a, b] = [lum(fg), lum(bg)];
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const dark = tokens(block(/@theme\b/));
const light = tokens(block(/:root\[data-theme=["']light["']\]/));

const THEMES: [string, Record<string, string>][] = [
  ["dark", dark],
  ["light", light],
];
const grounds = ["bg", "surface", "surface-2"];
const pairs: [string, string][] = [
  ...["text", "muted", "positive", "negative", "warning", "info"].flatMap((fg) =>
    grounds.map((bg) => [fg, bg] as [string, string]),
  ),
  ["accent", "bg"],
  ["accent", "surface"],
];

describe("theme tokens", () => {
  it("every dark token has a light counterpart", () => {
    const missing = Object.keys(dark).filter((k) => !(k in light));
    expect(missing, `tokens without light variant: ${missing.join(", ")}`).toEqual([]);
  });
});

describe.each(THEMES)("WCAG contrast (%s)", (name, t) => {
  it.each(pairs)("%s on %s >= 4.5:1", (fg, bg) => {
    const r = ratio(t[fg], t[bg]);
    expect(r, `${name}: ${fg} (${t[fg]}) on ${bg} (${t[bg]}) = ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });

  it("primary button text on accent >= 4.5:1 (bg or text token)", () => {
    const rb = ratio(t.bg, t.accent);
    const rt = ratio(t.text, t.accent);
    expect(
      Math.max(rb, rt),
      `${name}: bg on accent = ${rb.toFixed(2)}:1, text on accent = ${rt.toFixed(2)}:1 (accent ${t.accent})`,
    ).toBeGreaterThanOrEqual(4.5);
  });
});

// ---- extended guards ----------------------------------------------------


/** Resolve a tailwind "token[/alpha]" to a css color string with alpha. */
function withAlpha(t: Record<string, string>, tok: string): string {
  const [name, a] = tok.split("/");
  const [r, g, b, a0] = parse(t[name]);
  const alpha = a === undefined ? a0 : (Number(a) / 100) * a0;
  return `rgb(${r} ${g} ${b} / ${alpha})`;
}

function toneClasses(): [string, string, string][] {
  const src = badgeSrc;
  const body = /const tones = \{([\s\S]*?)\n\}/.exec(src)![1];
  return [...body.matchAll(/(\w+):\s*'bg-([\w/-]+)\s+text-([\w-]+)'/g)].map((m) => [m[1], m[2], m[3]]);
}

const selectionText = /checked \? '[^']*text-([\w-]+)'/.exec(toggleSrc)?.[1] ?? "accent";

const FLOORS = ["surface", "surface-2"];

describe.each(THEMES)("extended WCAG guards (%s)", (name, t) => {
  const check = (label: string, fg: string, bg: string, ground: string | undefined, min: number) => {
    const r = ratio(fg, bg, ground ? parse(t[ground]) : undefined);
    expect(r, `${name}: ${label} = ${r.toFixed(2)}:1 (need ${min})`).toBeGreaterThanOrEqual(min);
  };

  it("bg text on accent-strong (primary hover) >= 4.5", () => {
    check(`bg (${t.bg}) on accent-strong (${t["accent-strong"]})`, t.bg, t["accent-strong"], undefined, 4.5);
  });

  it.each(["surface", "bg"])("bg text on negative and negative/90 over %s >= 4.5", (g) => {
    check(`bg on negative`, t.bg, t.negative, undefined, 4.5);
    check(`bg on negative/90 over ${g}`, t.bg, withAlpha(t, "negative/90"), g, 4.5);
  });

  it.each(FLOORS)("selected toggle text (%s-based accent-soft) >= 4.5", (g) => {
    check(`${selectionText} on accent-soft over ${g}`, t[selectionText], t["accent-soft"], g, 4.5);
  });

  it.each(toneClasses())("Badge %s (bg-%s text-%s) >= 4.5 on surface and surface-2", (tone, bg, fg) => {
    for (const g of FLOORS) check(`Badge ${tone}: ${fg} on ${bg} over ${g}`, t[fg], withAlpha(t, bg), g, 4.5);
  });

  it("found Badge tones", () => {
    expect(toneClasses().length).toBeGreaterThanOrEqual(5);
  });

  it.each(["bg", "surface", "surface-2"])("accent focus ring vs %s >= 3:1", (g) => {
    check(`accent (${t.accent}) vs ${g} (${t[g]})`, t.accent, t[g], undefined, 3);
  });

  it.each(FLOORS)("input-border vs %s >= 3:1", (g) => {
    expect(t["input-border"], `${name}: --color-input-border missing`).toBeDefined();
    check(`input-border (${t["input-border"]}) vs ${g}`, t["input-border"], t[g], undefined, 3);
  });
});

function hue([r, g, b]: RGBA): number | null {
  const [R, G, B] = [r, g, b].map((c) => c / 255);
  const max = Math.max(R, G, B), min = Math.min(R, G, B), d = max - min;
  if (d < 0.08) return null; // near-grey: hue meaningless
  const h = max === R ? ((G - B) / d) % 6 : max === G ? (B - R) / d + 2 : (R - G) / d + 4;
  return (h * 60 + 360) % 360;
}

describe.each(THEMES)("allocation bucket colors (%s)", (name, t) => {
  // Decision: two segments are distinguishable if luminance ratio >= 1.5:1
  // OR hue differs by >= 30 degrees (chromatic pair). Applied to every pair.
  const src = profileSrc;
  const buckets = [...(/BUCKET_COLOR[^{]*\{([\s\S]*?)\}/.exec(src)?.[1] ?? "").matchAll(/(\w+):\s*'bg-([\w-]+)'/g)].map(
    (m) => [m[1], m[2]] as [string, string],
  );

  it("parses 4 buckets", () => expect(buckets.length).toBe(4));

  it("every pair is distinguishable", () => {
    for (let i = 0; i < buckets.length; i++)
      for (let j = i + 1; j < buckets.length; j++) {
        const [na, ta] = buckets[i], [nb, tb] = buckets[j];
        const ca = parse(t[ta]), cb = parse(t[tb]);
        const r = ratio(t[ta], t[tb]);
        const ha = hue(ca), hb = hue(cb);
        let dh = ha !== null && hb !== null ? Math.abs(ha - hb) : 0;
        dh = Math.min(dh, 360 - dh);
        expect(
          r >= 1.5 || dh >= 30,
          `${name}: ${na}(${ta} ${t[ta]}) vs ${nb}(${tb} ${t[tb]}): contrast ${r.toFixed(2)}:1, hue diff ${dh.toFixed(0)} deg`,
        ).toBe(true);
      }
  });
});
