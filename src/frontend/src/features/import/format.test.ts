import { describe, expect, it } from 'vitest'
import { commitMessage } from './format'

const base = { skipped_duplicates: 0, skipped_errors: 0 }

describe('commitMessage', () => {
  it.each([
    [1, 'Zaimportowano 1 transakcję'],
    [2, 'Zaimportowano 2 transakcje'],
    [5, 'Zaimportowano 5 transakcji'],
    [22, 'Zaimportowano 22 transakcje'],
  ])('%i', (n, expected) => {
    expect(commitMessage({ ...base, imported: n })).toBe(expected)
  })

  it('pomija duplikaty i błędy', () => {
    expect(commitMessage({ imported: 17, skipped_duplicates: 1, skipped_errors: 1 })).toBe(
      'Zaimportowano 17 transakcji, pominięto 1 duplikat i 1 błąd',
    )
    expect(commitMessage({ imported: 0, skipped_duplicates: 17, skipped_errors: 0 })).toBe(
      'Zaimportowano 0 transakcji, pominięto 17 duplikatów',
    )
  })
})
