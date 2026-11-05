import { describe, expect, it } from "vitest";
import * as mod from "./state";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const reducer: any = (mod as any).assistantReducer;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const phase = (s: any): string => s.status ?? s.kind ?? s.phase ?? s.state ?? s.type;

const summary = {
  month: "2026-10", income: "5000.00", expenses: "3000.00", balance: "2000.00",
  surplus: "2000.00", by_category: [],
};
const suggestion = {
  summary: "Odłóż nadwyżkę.", rationale: [{ claim: "a", refers_to: "budget", value: "1" }], risks: [], profile_used: true, id: 1, type: "surplus", month: "2026-10", disclaimer: "To nie jest porada.",
  model: "qwen3:8b", generated_at: "2026-11-05T10:00:00Z", duration_ms: 12345,
};
const resp = (ai_status: string, withSuggestion = false) => ({
  summary, ai_status, suggestion: withSuggestion ? suggestion : null, run_id: 7,
});

const idle = () => reducer(undefined, { type: "reset" });

describe("assistantReducer", () => {
  it("stan początkowy to idle", () => {
    expect(phase(idle())).toBe("idle");
  });

  it("start: idle -> loading", () => {
    expect(phase(reducer(idle(), { type: "start" }))).toBe("loading");
  });

  it("success z ai_status ok -> ok", () => {
    const s = reducer(reducer(idle(), { type: "start" }), { type: "success", response: resp("ok", true) });
    expect(phase(s)).toBe("ok");
    expect(JSON.stringify(s)).toContain("Odłóż nadwyżkę.");
  });

  it("success z ai_status unavailable -> unavailable", () => {
    const s = reducer(reducer(idle(), { type: "start" }), { type: "success", response: resp("unavailable") });
    expect(phase(s)).toBe("unavailable");
  });

  it("success z ai_status no_surplus -> no_surplus", () => {
    const s = reducer(reducer(idle(), { type: "start" }), { type: "success", response: resp("no_surplus") });
    expect(phase(s)).toBe("no_surplus");
  });

  it("failure: loading -> unavailable", () => {
    expect(phase(reducer(reducer(idle(), { type: "start" }), { type: "failure" }))).toBe("unavailable");
  });

  it("cancel: loading -> idle", () => {
    expect(phase(reducer(reducer(idle(), { type: "start" }), { type: "cancel" }))).toBe("idle");
  });

  it("reset wraca do idle z każdego stanu", () => {
    const loading = reducer(idle(), { type: "start" });
    const ok = reducer(loading, { type: "success", response: resp("ok", true) });
    const un = reducer(loading, { type: "failure" });
    for (const s of [loading, ok, un]) expect(phase(reducer(s, { type: "reset" }))).toBe("idle");
  });

  it("ponowny start z ok/unavailable -> loading", () => {
    const loading = reducer(idle(), { type: "start" });
    expect(phase(reducer(reducer(loading, { type: "failure" }), { type: "start" }))).toBe("loading");
    expect(phase(reducer(reducer(loading, { type: "success", response: resp("ok", true) }), { type: "start" }))).toBe("loading");
  });

  it("progress dopisuje kroki w kolejności", () => {
    let s = reducer(idle(), { type: "start" });
    s = reducer(s, { type: "progress", message: "Liczę podsumowanie miesiąca…" });
    s = reducer(s, { type: "progress", message: "Sprawdzam profil inwestycyjny…" });
    expect(phase(s)).toBe("loading");
    const j = JSON.stringify(s);
    expect(j).toContain("Liczę podsumowanie miesiąca…");
    expect(j.indexOf("Liczę")).toBeLessThan(j.indexOf("Sprawdzam"));
  });

  it("start czyści wcześniejsze kroki", () => {
    let s = reducer(idle(), { type: "start" });
    s = reducer(s, { type: "progress", message: "Krok-stary" });
    s = reducer(s, { type: "start" });
    expect(JSON.stringify(s)).not.toContain("Krok-stary");
  });

  it("success z ai_status limited -> limited", () => {
    const s = reducer(reducer(idle(), { type: "start" }), { type: "success", response: resp("limited") });
    expect(phase(s)).toBe("limited");
  });

  it("reset z limited -> idle", () => {
    const s = reducer(reducer(idle(), { type: "start" }), { type: "success", response: resp("limited") });
    expect(phase(reducer(s, { type: "reset" }))).toBe("idle");
  });
});
