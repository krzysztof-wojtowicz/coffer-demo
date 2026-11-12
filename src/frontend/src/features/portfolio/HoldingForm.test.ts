import { describe, expect, it } from 'vitest'
import { toBody } from './HoldingForm'
import type { Holding } from './queries'

const form = {
  name: 'Mieszkanie',
  asset_class: 'real_estate' as const,
  symbol: '',
  currency: 'PLN',
  quantity: '',
  purchase_price: '400000',
  purchase_date: '',
  manual_value: '',
  note: '',
}

describe('toBody', () => {
  it('create: fixed quantity 1 for hidden-quantity classes', () => {
    expect(toBody(form).quantity).toBe('1')
  })
  it('edit: keeps the stored quantity instead of the fixed 1', () => {
    const editing = { id: 1, quantity: '2.5000' } as unknown as Holding
    expect(toBody(form, editing).quantity).toBe('2.5000')
  })
  it('edit: visible quantity field still comes from the form', () => {
    const editing = { id: 1, quantity: '2' } as unknown as Holding
    expect(toBody({ ...form, asset_class: 'stock', quantity: '7' }, editing).quantity).toBe('7')
  })
})
