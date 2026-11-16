import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { pl } from '../../i18n/pl'
import { isSafeUrl } from '../../lib/url'
import { formatDate, formatFindingValue, formatValue } from './labels'
import { ApplyLimits } from './ApplyLimits'
import { Notice, SourceBadge } from './parts'
import type { Report } from './queries'

const A = pl.assistant

/** One renderer for every action report: headline + key figures, details on demand. */
export function ActionReport({
  report,
  source,
  aiStatus,
  runId,
  defaultOpen = false,
  showHeadline = true,
  action,
}: {
  report: Report
  source: string
  aiStatus?: string
  runId?: number | null
  defaultOpen?: boolean
  showHeadline?: boolean
  action?: string
}) {
  const statusMsg = aiStatus && aiStatus !== 'ok' ? A.aiStatus[aiStatus] : undefined
  const hasDetails =
    report.findings.length > 0 ||
    report.tables.length > 0 ||
    report.recommendations.length > 0 ||
    report.risks.length > 0 ||
    report.sources.length > 0
  return (
    <div className="space-y-3">
      {showHeadline && (
        <div className="flex flex-wrap items-start gap-2">
          <h3 className="text-base font-semibold text-text">{report.headline}</h3>
          <SourceBadge source={source} />
        </div>
      )}
      {statusMsg && <Notice>{statusMsg}</Notice>}
      {report.facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {report.facts.map((f, i) => (
            <div key={i} className="rounded-md bg-surface-2 p-2.5">
              <dt className="text-xs text-muted">{f.label}</dt>
              <dd className="text-sm font-semibold tabular-nums text-text">
                {formatValue(f.value, f.kind)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {hasDetails && (
        <details className="group rounded-md border border-border p-3" open={defaultOpen}>
          <summary className="cursor-pointer text-sm font-medium text-accent">
            {A.reportDetails}
          </summary>
          <div className="mt-3 space-y-4 text-sm">
            {report.findings.length > 0 && (
              <section>
                <h4 className="mb-1 font-semibold">{A.findings}</h4>
                <ul className="space-y-1.5">
                  {report.findings.map((f, i) => (
                    <li key={i}>
                      <span className="font-medium">{f.title}</span>{' '}
                      <Badge>{A.refersTo[f.refers_to] ?? f.refers_to}</Badge>
                      {f.value && <span className="ml-1 tabular-nums text-muted">{formatFindingValue(f.value)}</span>}
                      <p className="text-muted">{f.detail}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {report.tables.map((t) => (
              <section key={t.id}>
                <h4 className="mb-1 font-semibold">{t.title}</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <caption className="sr-only">{t.title}</caption>
                    <thead className="text-muted">
                      <tr>
                        {t.columns.map((c) => (
                          <th key={c.key} scope="col" className="py-1 pr-3 font-medium">
                            {c.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {t.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border">
                          {t.columns.map((c, ci) =>
                            ci === 0 ? (
                              <th key={c.key} scope="row" className="py-1 pr-3 text-left font-normal">
                                {formatValue(r[c.key] ?? '', c.kind)}
                              </th>
                            ) : (
                              <td key={c.key} className="py-1 pr-3 tabular-nums">
                                {formatValue(r[c.key] ?? '', c.kind)}
                              </td>
                            ),
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
            {report.recommendations.length > 0 && (
              <section>
                <h4 className="mb-1 font-semibold">{A.recommendations}</h4>
                <ul className="space-y-2">
                  {report.recommendations.map((r, i) => (
                    <li key={i} className="rounded-md bg-surface-2 p-2.5">
                      <p className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{r.title}</span>
                        {r.symbol && <Badge tone="info">{r.symbol}</Badge>}
                        {r.risk_level != null && <Badge tone="warning">{A.riskLevel(r.risk_level)}</Badge>}
                        {r.amount && (
                          <span className="tabular-nums">{formatValue(r.amount, 'money')}</span>
                        )}
                      </p>
                      <p className="text-muted">{r.detail}</p>
                      {r.source_url && isSafeUrl(r.source_url) && (
                        <a
                          className="text-accent hover:underline"
                          href={r.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {A.sourcesTitle}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {report.risks.length > 0 && (
              <section>
                <h4 className="mb-1 font-semibold">{A.risks}</h4>
                <ul className="list-disc pl-5">
                  {report.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </section>
            )}
            {report.sources.length > 0 && (
              <section>
                <h4 className="mb-1 font-semibold">{A.sourcesTitle}</h4>
                <ul className="space-y-1">
                  {report.sources.map((s, i) => (
                    <li key={i}>
                      {isSafeUrl(s.url) ? (
                      <a
                        className="text-accent hover:underline"
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {s.title}
                      </a>
                      ) : (
                        <span>{s.title}</span>
                      )}
                      <span className="text-muted">
                        {s.publisher ? ` · ${s.publisher}` : ''} · {A.fetchedAt(formatDate(s.fetched_at))}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </details>
      )}
      {action === 'budget_plan' && <ApplyLimits report={report} />}
      <p className="text-xs text-muted">{report.disclaimer}</p>
      {runId != null && (
        <Link className="text-xs text-accent hover:underline" to={`/assistant/runs/${runId}`}>
          {A.showTrace}
        </Link>
      )}
    </div>
  )
}
