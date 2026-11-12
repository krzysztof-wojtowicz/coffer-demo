import { useEffect, useState, type KeyboardEvent } from 'react'
import { Card } from '../../components/ui/Card'
import type { components } from '../../api/schema'
import { cn } from '../../lib/cn'
import { pl } from '../../i18n/pl'
import type { AdviceHoldingIn } from '../portfolio/queries'
import { AdvisorPanel } from './AdvisorPanel'
import { AssistantPanel } from './AssistantPanel'
import { AiStatusBadge } from './parts'
import { fetchAgentStatus, type AgentStatus } from './queries'

type Summary = components['schemas']['MonthSummaryOut']
type Mode = 'surplus' | 'portfolio'


/** One AI panel: shared header and status, a mode switch and one result area. */
export function AiPanel({
  month,
  summary,
  holdings,
}: {
  month: string
  summary: Summary | null
  holdings: AdviceHoldingIn[]
}) {
  const a = pl.assistant
  // Without a budget summary (query failed) only the portfolio advisor works.
  const MODES: Mode[] = summary ? ['surplus', 'portfolio'] : ['portfolio']
  const [mode, setMode] = useState<Mode>(summary ? 'surplus' : 'portfolio')
  const [agent, setAgent] = useState<AgentStatus | null>(null)

  useEffect(() => {
    const ctl = new AbortController()
    void fetchAgentStatus(ctl.signal).then((s) => {
      if (!ctl.signal.aborted) setAgent(s)
    })
    return () => ctl.abort()
  }, [])

  const onTabKey = (e: KeyboardEvent<HTMLButtonElement>, m: Mode) => {
    const i = MODES.indexOf(m)
    let next: Mode | undefined
    if (e.key === 'ArrowRight') next = MODES[(i + 1) % MODES.length]
    else if (e.key === 'ArrowLeft') next = MODES[(i + MODES.length - 1) % MODES.length]
    else if (e.key === 'Home') next = MODES[0]
    else if (e.key === 'End') next = MODES[MODES.length - 1]
    if (!next) return
    e.preventDefault()
    setMode(next)
    document.getElementById(`ai-tab-${next}`)?.focus()
  }

  return (
    <Card title={a.title} actions={<AiStatusBadge status={agent} />}>
      <div role="tablist" aria-label={a.title} className="mb-4 inline-flex rounded-lg border border-border bg-surface-2 p-0.5">
        {MODES.map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            id={`ai-tab-${m}`}
            aria-selected={mode === m}
            tabIndex={mode === m ? 0 : -1}
            onKeyDown={(e) => onTabKey(e, m)}
            aria-controls={`ai-panel-${m}`}
            onClick={() => setMode(m)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              mode === m ? 'bg-accent text-white shadow-sm' : 'text-muted hover:text-text',
            )}
          >
            {a.modes[m]}
          </button>
        ))}
      </div>
      {/* Both stay mounted so switching tabs does not abort a running request. */}
      {summary && (
        <div role="tabpanel" id="ai-panel-surplus" aria-labelledby="ai-tab-surplus" hidden={mode !== 'surplus'}>
          <AssistantPanel month={month} summary={summary} agent={agent} />
        </div>
      )}
      <div role="tabpanel" id="ai-panel-portfolio" aria-labelledby="ai-tab-portfolio" hidden={mode !== 'portfolio'}>
        <AdvisorPanel holdings={holdings} />
      </div>
    </Card>
  )
}
