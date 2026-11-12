import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Notice } from './parts'
import { pl } from '../../i18n/pl'
import { AdviceError, useInvestmentAdvice, type AdviceHoldingIn } from '../portfolio/queries'

const t = pl.portfolio.advisor

// Defense in depth: URLs come from news feeds / LLM, so only http(s) may become a link.
function isHttpUrl(url: string): boolean {
  try {
    return ['http:', 'https:'].includes(new URL(url).protocol)
  } catch {
    return false
  }
}

function SourceLink({ url, label }: { url: string | null | undefined; label: string }) {
  if (!url || !isHttpUrl(url)) return <span>{label}</span>
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" className="text-accent underline">
      {label}
    </a>
  )
}

export function AdvisorPanel({ holdings }: { holdings: AdviceHoldingIn[] }) {
  const advice = useInvestmentAdvice()
  const qc = useQueryClient()
  const error = advice.error
    ? advice.error instanceof AdviceError
      ? advice.error.message
      : t.error
    : null
  const data = advice.data

  useEffect(() => {
    if (data) void qc.invalidateQueries({ queryKey: ['agent'] })
  }, [data, qc])

  return (
    <div className="space-y-3">
      <p className="text-text">{t.intro}</p>
      <div className="flex items-center gap-3">
        <Button loading={advice.isPending} onClick={() => advice.mutate(holdings)}>
          {data ? t.refetch : t.fetch}
        </Button>
        {advice.isPending && (
          <span className="flex items-center gap-2 text-sm text-muted" aria-live="polite">
            <Spinner />
            {t.loading}
          </span>
        )}
      </div>
      <ErrorMessage message={error} />
      {data && (
        <div className="mt-4 space-y-5">
          <section>
            <h3 className="mb-2 text-sm font-semibold">{t.topPicks}</h3>
            <ul className="grid gap-3 sm:grid-cols-3">
              {data.top_picks.slice(0, 3).map((p, i) => (
                <li
                  key={`${p.symbol ?? p.name}-${i}`}
                  className="rounded-md border border-border bg-surface-2 p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <strong>{p.name}</strong>
                    {p.symbol && <Badge tone="info">{p.symbol}</Badge>}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {pl.portfolio.classes[p.asset_class] ?? p.asset_class} · {t.risk}:{' '}
                    {p.risk_level}
                  </div>
                  <p className="mt-2">{p.rationale}</p>
                  {p.source_url && (
                    <p className="mt-2 text-xs">
                      <SourceLink url={p.source_url} label={t.source} />
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
          {data.tips.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold">{t.tips}</h3>
              <ul className="space-y-2 text-sm">
                {data.tips.map((tip, i) => (
                  <li key={`${tip.title}-${i}`}>
                    <strong>{tip.title}</strong>
                    <p>{tip.summary}</p>
                    <p className="text-xs text-muted">
                      {t.source}: <SourceLink url={tip.url} label={tip.source} />
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {!data.llm_used && (
            <div data-testid="advisor-ai-status">
              <Notice>
                {data.ai_status === 'timeout'
                  ? t.timeout
                  : data.ai_status === 'limited'
                    ? t.limited
                    : t.noLlm}
              </Notice>
            </div>
          )}
          <p
            className="flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-2 text-sm text-warning"
            data-testid="advisor-disclaimer"
          >
            <span aria-hidden="true">ⓘ</span>
            <span>{data.disclaimer}</span>
          </p>
          {data.run_id != null && (
            <p className="text-xs">
              <Link className="text-accent hover:underline" to={`/assistant/runs/${data.run_id}`}>
                {pl.assistant.showTrace}
              </Link>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
