const fmt = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

export function formatMoney(value: string): string {
  return fmt.format(Number(value))
}
