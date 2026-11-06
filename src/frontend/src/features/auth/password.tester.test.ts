// Tester: frontend password rules must give the same result as the backend
// (src/backend/coffer/accounts/policy.py). Expected values were produced by running the Python
// policy on exactly these inputs (email: jan.kowalski@example.com).
import { describe, expect, it } from "vitest";
import { passwordProblems, passwordStrength } from "./password";

type Case = { password: string; email: string; problems: string[] };
const SAME: Case[] = [
  {
    password: "Abcdefghij1",
    email: "jan.kowalski@example.com",
    problems: ["Has\u0142o musi mie\u0107 co najmniej 12 znak\u00f3w."],
  },
  { password: "Abcdefghij12", email: "jan.kowalski@example.com", problems: [] },
  {
    password:
      "Ab1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password:
      "Ab1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    email: "jan.kowalski@example.com",
    problems: ["Has\u0142o mo\u017ce mie\u0107 najwy\u017cej 128 znak\u00f3w."],
  },
  {
    password: "za\u017c\u00f3\u0142\u0107g\u0119\u015bl\u0105",
    email: "jan.kowalski@example.com",
    problems: ["Has\u0142o musi mie\u0107 co najmniej 12 znak\u00f3w."],
  },
  {
    password: "za\u017c\u00f3\u0142\u0107g\u0119\u015bl\u0105j",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password:
      "\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00\ud83d\ude00",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
    ],
  },
  {
    password:
      "\ud83d\ude00\ud83d\ude01\ud83d\ude02\ud83e\udd23\ud83d\ude03\ud83d\ude04\ud83d\ude05\ud83d\ude06\ud83d\ude07\ud83d\ude08\ud83d\ude09\ud83d\ude0a",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password:
      "\ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d\udc66\ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d\udc66",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password: "            ",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
    ],
  },
  { password: "a b c d e f ", email: "jan.kowalski@example.com", problems: [] },
  {
    password: "  jan.kowalski  ",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o nie mo\u017ce by\u0107 takie samo jak adres e-mail.",
    ],
  },
  {
    password: "JAN.KOWALSKI",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o nie mo\u017ce by\u0107 takie samo jak adres e-mail.",
    ],
  },
  {
    password: " password123 ",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password: "aaaaaaaaaaaa",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
      "To has\u0142o jest zbyt popularne. Wybierz inne.",
    ],
  },
  {
    password: "abcdabcdabcd",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
    ],
  },
  { password: "abcdeabcdeab", email: "jan.kowalski@example.com", problems: [] },
  {
    password: "e\u0301e\u0301e\u0301e\u0301e\u0301e\u0301",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
    ],
  },
  {
    password: "\u0130\u0130\u0130\u0130\u0130\u0130abcdef",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password: "\u03a3\u03a3\u03a3\u03a3\u03a3\u03a3abcdef",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password:
      "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o mo\u017ce mie\u0107 najwy\u017cej 128 znak\u00f3w.",
      "Has\u0142o musi zawiera\u0107 co najmniej 5 r\u00f3\u017cnych znak\u00f3w.",
    ],
  },
  {
    password: "Haslo z\u00a0spacj\u01051",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password: "\u00a0jan.kowalski\u00a0",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o nie mo\u017ce by\u0107 takie samo jak adres e-mail.",
    ],
  },
];
// Python str.strip() and JS trim() strip different characters (U+FEFF, U+001C-001F, U+0085).
const DIVERGENT: Case[] = [
  {
    password: "jan.kowalski\ufeff",
    email: "jan.kowalski@example.com",
    problems: [],
  },
  {
    password: "jan.kowalski\u001f",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o nie mo\u017ce by\u0107 takie samo jak adres e-mail.",
    ],
  },
  {
    password: "jan.kowalski\u0085",
    email: "jan.kowalski@example.com",
    problems: [
      "Has\u0142o nie mo\u017ce by\u0107 takie samo jak adres e-mail.",
    ],
  },
];

describe("polityka haseł: front = backend", () => {
  it.each(SAME)("$password", ({ password, email, problems }) => {
    expect(passwordProblems(password, email)).toEqual(problems);
  });
  // BUG (low, accounts): known divergence; flip to it.each when fixed.
  it.each(DIVERGENT)(
    "rozbieżność białych znaków: $password",
    ({ password, email, problems }) => {
      expect(passwordProblems(password, email)).toEqual(problems);
    },
  );
});

describe("granice długości", () => {
  const base = "Ab1-xyz";
  it.each([
    [11, false],
    [12, true],
    [128, true],
    [129, false],
  ])("%i znaków -> poprawne: %s", (n, valid) => {
    const pw = base + "q".repeat(n - base.length);
    expect(passwordProblems(pw, "jan@example.com").length === 0).toBe(valid);
  });
});

describe("wskaźnik siły", () => {
  it("rośnie z długością i różnorodnością, słabe hasło najwyżej 1", () => {
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("aaaaaaaaaaaaaaaaaaaaaaa")).toBeLessThanOrEqual(1);
    expect(passwordStrength("password123", "a@b.pl")).toBeLessThanOrEqual(1);
    const mid = passwordStrength("kot-w-butach");
    const strong = passwordStrength("Kot-w-butach-42-i-pies!");
    expect(strong).toBeGreaterThan(mid);
    expect(strong).toBeLessThanOrEqual(4);
  });
});
