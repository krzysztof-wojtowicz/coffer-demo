// Same rules as the backend (src/backend/coffer/accounts/policy.py); the server stays the
// source of truth, this only gives instant feedback (UC-01 4b).
import commonList from './commonPasswords.json'

export const MIN_LENGTH = 12
export const MAX_LENGTH = 128
export const MIN_DISTINCT_CHARS = 5

const COMMON = new Set<string>(commonList as string[])

/** Same set as WHITESPACE in policy.py (= Python str.isspace()); JS trim() differs. */
export const WHITESPACE =
  '\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004' +
  '\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'

function strip(s: string): string {
  let start = 0
  let end = s.length
  while (start < end && WHITESPACE.includes(s[start])) start++
  while (end > start && WHITESPACE.includes(s[end - 1])) end--
  return s.slice(start, end)
}

/** Python's len() counts code points, so do we (not UTF-16 units). */
const length = (s: string) => [...s].length

export function passwordProblems(password: string, email: string): string[] {
  const problems: string[] = []
  const n = length(password)
  if (n < MIN_LENGTH) problems.push(`Hasło musi mieć co najmniej ${MIN_LENGTH} znaków.`)
  if (n > MAX_LENGTH) problems.push(`Hasło może mieć najwyżej ${MAX_LENGTH} znaków.`)
  if (new Set(password).size < MIN_DISTINCT_CHARS)
    problems.push(`Hasło musi zawierać co najmniej ${MIN_DISTINCT_CHARS} różnych znaków.`)
  const lowered = strip(password).toLowerCase()
  const mail = strip(email).toLowerCase()
  if (lowered && (lowered === mail || lowered === mail.split('@')[0]))
    problems.push('Hasło nie może być takie samo jak adres e-mail.')
  if (COMMON.has(lowered)) problems.push('To hasło jest zbyt popularne. Wybierz inne.')
  return problems
}

/** Rough strength score 0..4 for the meter (rules above decide validity, not this). */
export function passwordStrength(password: string, email = ''): number {
  if (!password) return 0
  const n = length(password)
  const classes = [/[a-ząćęłńóśźż]/, /[A-ZĄĆĘŁŃÓŚŹŻ]/, /\d/, /[^\p{L}\d]/u].filter((r) =>
    r.test(password),
  ).length
  let score = 0
  if (n >= MIN_LENGTH) score++
  if (n >= 16) score++
  if (n >= 20) score++
  if (classes >= 3) score++
  if (passwordProblems(password, email).length > 0) score = Math.min(score, 1)
  return Math.min(score, 4)
}
