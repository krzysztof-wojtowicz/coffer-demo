import { expect, test } from 'vitest'
import { formatMoney } from './money'

test('formatMoney formats PLN', () => {
  const s = formatMoney('-1234.5')
  expect(s).toContain('1234,50')
  expect(s).toContain('zł')
})
