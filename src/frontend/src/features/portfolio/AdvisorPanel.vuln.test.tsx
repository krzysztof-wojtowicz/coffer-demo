import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AdvisorPanel } from './AdvisorPanel'

// Attack: a poisoned news feed / LLM answer smuggles a javascript: URL into source links.
const advice = {
  top_picks: [
    {
      name: 'Evil',
      symbol: null,
      asset_class: 'stock',
      risk_level: 'high',
      rationale: 'x',
      source_url: 'javascript:alert(document.cookie)',
    },
  ],
  tips: [
    { title: 'T1', summary: 's', source: 'evil', url: ' JaVaScRiPt:alert(1)' },
    { title: 'T2', summary: 's', source: 'data', url: 'data:text/html,<script>alert(1)</script>' },
    { title: 'T3', summary: 's', source: 'ok', url: 'https://example.com/news' },
  ],
  llm_used: true,
  ai_status: 'ok',
  disclaimer: 'd',
}
vi.mock('./queries', () => ({
  AdviceError: class extends Error {},
  useInvestmentAdvice: () => ({ data: advice, error: null, isPending: false, mutate: () => {} }),
}))

afterEach(cleanup)

describe('AdvisorPanel link safety', () => {
  it('renders only http(s) links, with noopener noreferrer', () => {
    render(<AdvisorPanel holdings={[]} />)
    const links = screen.getAllByRole('link')
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['https://example.com/news'])
    expect(links[0].getAttribute('rel')).toContain('noopener')
    expect(links[0].getAttribute('rel')).toContain('noreferrer')
    // Unsafe sources still show their label as plain text.
    expect(screen.getByText('evil')).toBeTruthy()
  })
})
