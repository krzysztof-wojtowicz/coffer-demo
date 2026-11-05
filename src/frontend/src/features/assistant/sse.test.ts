import { describe, expect, it } from "vitest";
import * as mod from "./sse";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const parseSse: any = (mod as any).parseSse;

describe("parseSse", () => {
  it("jedno zdarzenie", () => {
    const r = parseSse('event: status\ndata: {"message":"Liczę"}\n\n', "");
    expect(r.events).toEqual([{ event: "status", data: '{"message":"Liczę"}' }]);
    expect(r.rest).toBe("");
  });

  it("kilka zdarzeń w jednym kawałku", () => {
    const r = parseSse("event: status\ndata: a\n\nevent: summary\ndata: b\n\nevent: result\ndata: c\n\n", "");
    expect(r.events.map((e: { event: string }) => e.event)).toEqual(["status", "summary", "result"]);
    expect(r.events.map((e: { data: string }) => e.data)).toEqual(["a", "b", "c"]);
    expect(r.rest).toBe("");
  });

  it("zdarzenie rozcięte między kawałkami", () => {
    const r1 = parseSse("event: sta", "");
    expect(r1.events).toEqual([]);
    const r2 = parseSse('tus\ndata: {"message":"x', r1.rest);
    expect(r2.events).toEqual([]);
    const r3 = parseSse('y"}\n\nevent: result\nda', r2.rest);
    expect(r3.events).toEqual([{ event: "status", data: '{"message":"xy"}' }]);
    const r4 = parseSse("ta: z\n\n", r3.rest);
    expect(r4.events).toEqual([{ event: "result", data: "z" }]);
    expect(r4.rest).toBe("");
  });

  it("niepełne zdarzenie zostaje w rest", () => {
    const r = parseSse("event: status\ndata: a\n\nevent: summary\ndata: b", "");
    expect(r.events.length).toBe(1);
    expect(r.rest).toContain("summary");
  });

  it("ignoruje komentarze zaczynające się od dwukropka", () => {
    const r = parseSse(": keepalive\n\nevent: status\ndata: a\n: komentarz\n\n", "");
    expect(r.events).toEqual([{ event: "status", data: "a" }]);
  });
});
