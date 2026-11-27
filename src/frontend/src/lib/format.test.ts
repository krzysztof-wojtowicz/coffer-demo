import { expect, test } from 'vitest'
import { formatMoney, formatPct, signOf } from './format'

test('formatMoney formats negative PLN', () => {
  const s = formatMoney('-1234.5')
  expect(s).toContain('1234,50')
  expect(s).toContain('zł')
})

test('formatMoney handles zero and other currencies', () => {
  expect(formatMoney('0.00')).toContain('0,00')
  expect(formatMoney('10', 'USD')).toContain('USD')
})

test('formatMoney falls back for an unknown currency', () => {
  expect(formatMoney('12.50', 'not-a-ccy')).toBe('12.50 not-a-ccy')
})

test('signOf treats -0.00 as zero', () => {
  expect(signOf('-0.00')).toBe(0)
  expect(signOf('0')).toBe(0)
  expect(signOf('-3.1')).toBe(-1)
  expect(signOf('2')).toBe(1)
})

test('formatPct uses a decimal comma, optional plus and a dash for null', () => {
  expect(formatPct('62.4')).toBe('62,4%')
  expect(formatPct('3.1', { signed: true })).toBe('+3,1%')
  expect(formatPct('-3.1', { signed: true })).toBe('-3,1%')
  expect(formatPct('0.0', { signed: true })).toBe('0,0%')
  expect(formatPct(null)).toBe('–')
})
