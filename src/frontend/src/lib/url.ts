/** True only for absolute http/https URLs (blocks javascript:, data:, etc.). */
export function isSafeUrl(url: string | null | undefined): boolean {
  if (!url) return false
  try {
    const p = new URL(url).protocol
    return p === 'http:' || p === 'https:'
  } catch {
    return false
  }
}
