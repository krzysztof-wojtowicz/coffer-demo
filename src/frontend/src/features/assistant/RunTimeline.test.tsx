import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { RunTimeline } from './RunTimeline'

afterEach(cleanup)

const steps = [
  { index: 0, kind: 'tool', name: 'get_portfolio', started_ms: 0, duration_ms: 20, status: 'ok', arguments: { a: 1 }, output: { total: '5' }, error: null, origin: 'prepare' },
  { index: 1, kind: 'llm', name: 'llm', started_ms: 20, duration_ms: 80, status: 'ok', provider: 'gemini', model: 'g', attempt: 1, input_tokens: 10, output_tokens: 5, cost_usd: null, output: 'surowa' },
  { index: 2, kind: 'validation', name: 'validation', started_ms: 100, duration_ms: 1, status: 'error', errors: ['zły format'] },
]

describe('RunTimeline', () => {
  it('expands step details with keyboard-accessible buttons', async () => {
    render(<RunTimeline steps={steps} totalMs={101} />)
    expect(screen.getByText('Portfel')).toBeTruthy()
    const btn = screen.getAllByRole('button')[0]
    expect(btn.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('Argumenty')).toBeNull()
    await userEvent.click(btn)
    expect(btn.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText('Argumenty')).toBeTruthy()
    expect(screen.getByText(/"total": "5"/)).toBeTruthy()
    await userEvent.click(screen.getAllByRole('button')[2])
    expect(screen.getByText('zły format')).toBeTruthy()
  })
})
