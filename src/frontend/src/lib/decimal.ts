/** Compare two decimal strings without floats (sign, then integer and fraction digits). */
export function compareAmounts(a: string, b: string): number {
  const norm = (v: string) => {
    const neg = v.trim().startsWith('-')
    const [i = '0', f = ''] = v.trim().replace(/^[-+]/, '').split('.')
    const digits = BigInt(i + f.padEnd(6, '0').slice(0, 6))
    return neg ? -digits : digits
  }
  const x = norm(a)
  const y = norm(b)
  return x < y ? -1 : x > y ? 1 : 0
}
