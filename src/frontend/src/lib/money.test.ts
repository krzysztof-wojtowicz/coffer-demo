import { expect, test } from 'vitest'
import { aiStatusMessage } from './errors'
import { formatMoney } from './money'
import { pl } from '../i18n/pl'

test('formatMoney formats PLN', () => {
  const s = formatMoney('-1234.5')
  expect(s).toContain('1234,50')
  expect(s).toContain('zł')
})

test('aiStatusMessage maps statuses', () => {
  expect(aiStatusMessage('ok')).toBeNull()
  expect(aiStatusMessage('no_surplus')).toBe(pl.assistant.noSurplus)
  expect(aiStatusMessage('unavailable')).toBe(pl.assistant.unavailable)
})
