import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import { AdviceError, useInvestmentAdvice, type AdviceHoldingIn } from './queries'

const t = pl.portfolio.advisor

function SourceLink({ url, label }: { url: string | null | undefined; label: string }) {
  if (!url) return <span>{label}</span>
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" className="text-accent underline">
      {label}
    </a>
  )
}

export function AdvisorPanel({ holdings }: { holdings: AdviceHoldingIn[] }) {
  const advice = useInvestmentAdvice()
  const error = advice.error
    ? advice.error instanceof AdviceError
      ? advice.error.message
      : t.error
    : null
  const data = advice.data

  return (
    <Card
      title={t.title}
      actions={
        <Button size="sm" loading={advice.isPending} onClick={() => advice.mutate(holdings)}>
          {t.fetch}
        </Button>
      }
    >
      <p className="text-sm text-muted">{t.intro}</p>
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
          {!data.llm_used && <p className="text-xs text-muted">{t.noLlm}</p>}
          <p className="text-xs text-muted" data-testid="advisor-disclaimer">
            {data.disclaimer}
          </p>
        </div>
      )}
    </Card>
  )
}
