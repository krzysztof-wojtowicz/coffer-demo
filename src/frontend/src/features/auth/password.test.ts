import { describe, expect, it } from 'vitest'
import { passwordProblems, passwordStrength } from './password'

describe('passwordProblems', () => {
  it('akceptuje dobre hasło', () => {
    expect(passwordProblems('Kot-w-butach-42', 'jan@example.com')).toEqual([])
  })
  it('wymaga 12 znaków i 5 różnych znaków', () => {
    expect(passwordProblems('aaaa', 'a@b.pl')).toHaveLength(2)
  })
  it('odrzuca hasło równe e-mailowi lub jego części przed @', () => {
    expect(passwordProblems('Jan.Kowalski@example.com', 'jan.kowalski@example.com')).toContain(
      'Hasło nie może być takie samo jak adres e-mail.',
    )
    expect(passwordProblems('jan.kowalski', 'jan.kowalski@example.com')).toContain(
      'Hasło nie może być takie samo jak adres e-mail.',
    )
  })
  it('odrzuca popularne hasło bez względu na wielkość liter', () => {
    expect(passwordProblems('QWERTY123456', 'a@b.pl')).toContain(
      'To hasło jest zbyt popularne. Wybierz inne.',
    )
  })
  it('liczy znaki jak backend (punkty kodowe)', () => {
    expect(passwordProblems('😀'.repeat(6) + 'abcde1', 'a@b.pl')).toEqual([])
    expect(passwordProblems('x'.repeat(129), 'a@b.pl')).toContain(
      'Hasło może mieć najwyżej 128 znaków.',
    )
  })
})

describe('passwordStrength', () => {
  it('rośnie z długością i różnorodnością', () => {
    expect(passwordStrength('')).toBe(0)
    expect(passwordStrength('abc')).toBe(0)
    expect(passwordStrength('password1234')).toBeLessThanOrEqual(1)
    expect(passwordStrength('kotwbutachdwa')).toBe(1)
    expect(passwordStrength('Kot-w-butach-42-i-pies')).toBe(4)
  })
})
