const pad = (n: number) => String(n).padStart(2, '0')

/** YYYY-MM-DD in the browser's local time zone (never via toISOString, which is UTC). */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export const todayIso = () => isoDate(new Date())
