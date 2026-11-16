import type { ReactNode } from 'react'
import { Badge } from '../../components/ui/Badge'
import { pl } from '../../i18n/pl'
import type { AgentStatus } from './queries'

export function Notice({ children }: { children: ReactNode }) {
  return <p className="rounded-md bg-warning/10 p-3 text-sm text-warning">{children}</p>
}

export function AiStatusBadge({ status }: { status: AgentStatus | null }) {
  if (!status) return null
  if (status.provider === 'none') return <Badge tone="neutral">{pl.assistant.statusOff}</Badge>
  if (status.available) return <Badge tone="success">{pl.assistant.statusAvailable}</Badge>
  return <Badge tone="warning">{pl.assistant.statusUnavailable}</Badge>
}

export function SourceBadge({ source }: { source: string }) {
  return source === 'ai' ? (
    <Badge tone="info">{pl.assistant.sourceAi}</Badge>
  ) : (
    <Badge tone="neutral">{pl.assistant.sourceRules}</Badge>
  )
}

const pretty = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2))

export function Pre({ children }: { children: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-bg p-2 text-xs text-text">
      {pretty(children)}
    </pre>
  )
}
