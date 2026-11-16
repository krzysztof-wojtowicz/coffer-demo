import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { ActionReport } from './ActionReport'
import type { Report } from './queries'

afterEach(cleanup)

const base: Report = {
  headline: 'Nagłówek',
  facts: [{ label: 'Wydatki', value: '100.00', kind: 'money' }],
  tables: [],
  findings: [{ title: 'Ustalenie', detail: 'Opis', refers_to: 'budget', value: null }],
  recommendations: [],
  risks: [],
  sources: [
    { title: 'Artykuł', url: 'https://example.com/a', publisher: 'Wydawca', published_at: null, fetched_at: '2026-11-10T10:00:00Z' },
  ],
  disclaimer: 'Zastrzeżenie F33',
}

const view = (props: Partial<Parameters<typeof ActionReport>[0]> = {}) =>
  render(
    <MemoryRouter>
      <ActionReport report={base} source="rules" aiStatus="unavailable" {...props} />
    </MemoryRouter>,
  )

describe('ActionReport', () => {
  it('shows the rules badge, the AI status message and the disclaimer', () => {
    view()
    expect(screen.getByText('Reguły')).toBeTruthy()
    expect(screen.getByText(/Model AI jest niedostępny/)).toBeTruthy()
    expect(screen.getByText('Zastrzeżenie F33')).toBeTruthy()
  })

  it('shows sources with the fetch date and safe link attributes', () => {
    view()
    const link = screen.getByRole('link', { name: 'Artykuł' })
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(screen.getByText(/pobrano: 10\.11\.2026/)).toBeTruthy()
  })

  it('shows the AI badge for ai source without a status notice', () => {
    view({ source: 'ai', aiStatus: 'ok' })
    expect(screen.getByText('AI')).toBeTruthy()
    expect(screen.queryByText(/wynik przygotowano regułami/)).toBeNull()
  })

  it('does not render links for non-http(s) URLs', () => {
    view({
      report: {
        ...base,
        sources: [{ ...base.sources[0], url: 'javascript:alert(1)' }],
        recommendations: [
          { title: 'R', detail: 'd', symbol: null, asset_class: null, amount: null, risk_level: null, source_url: 'data:text/html,x' },
        ],
      },
    })
    expect(screen.queryByRole('link', { name: 'Artykuł' })).toBeNull()
    expect(screen.getByText('Artykuł')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Źródła' })).toBeNull()
  })
})
