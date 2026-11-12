import { useRef, useState, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Money } from '../../components/Money'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { useCategories } from '../transactions/queries'
import { commitButtonLabel, commitMessage, pluralForm } from './format'
import {
  ApiError,
  useBanks,
  useCancel,
  useCommit,
  useUpload,
  type CommitResult,
  type ImportPreview,
  type ImportRow,
} from './queries'

type Filter = 'all' | ImportRow['status']

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}

export function ImportFlow({ onFinished }: { onFinished?: () => void }) {
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [result, setResult] = useState<CommitResult | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const reset = (message: string | null = null) => {
    setPreview(null)
    setResult(null)
    setNotice(message)
  }

  return (
    <>
      {result ? (
        <ResultStep result={result} onAnother={() => reset()} onFinished={onFinished} />
      ) : preview ? (
        <PreviewStep
          key={preview.id}
          preview={preview}
          onDone={setResult}
          onReset={reset}
        />
      ) : (
        <UploadStep notice={notice} onPreview={(p) => { setNotice(null); setPreview(p) }} />
      )}
    </>
  )
}

function UploadStep({
  notice,
  onPreview,
}: {
  notice: string | null
  onPreview: (p: ImportPreview) => void
}) {
  const banks = useBanks()
  const upload = useUpload()
  const [bank, setBank] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const bankId = bank || banks.data?.[0]?.id || ''

  const pick = (f: File | undefined) => {
    if (f) {
      setFile(f)
      setLocalError(null)
      upload.reset()
    }
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files[0])
  }
  const submit = () => {
    if (!file) return setLocalError(pl.import.noFile)
    upload.mutate({ file, bank: bankId }, { onSuccess: onPreview })
  }

  const error = localError ?? (upload.error ? apiErrorMessage(upload.error) : null)

  return (
    <Card>
      <div className="flex max-w-xl flex-col gap-4">
        <ErrorMessage message={notice} />
        <ErrorMessage message={error} />
        <Field label={pl.import.bank}>
          <Select value={bankId} onChange={(e) => setBank(e.target.value)}>
            {banks.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        </Field>
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
          }}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed p-8 text-center text-muted ${
            dragging ? 'border-accent bg-accent-soft' : 'border-border'
          }`}
        >
          <span>{pl.import.dropzone}</span>
          {file && (
            <span className="text-sm font-medium text-text">
              {file.name} ({formatSize(file.size)})
            </span>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>
        <div>
          <Button onClick={submit} loading={upload.isPending} disabled={!bankId}>
            {pl.import.loadPreview}
          </Button>
        </div>
      </div>
    </Card>
  )
}

function PreviewStep({
  preview,
  onDone,
  onReset,
}: {
  preview: ImportPreview
  onDone: (r: CommitResult) => void
  onReset: (message?: string | null) => void
}) {
  const categories = useCategories()
  const commit = useCommit()
  const cancel = useCancel()
  const [filter, setFilter] = useState<Filter>('all')
  const [includeOv, setIncludeOv] = useState<Record<number, boolean>>({})
  const [catOv, setCatOv] = useState<Record<number, number>>({})

  const defaultCat = categories.data?.find((c) => c.is_default)?.id ?? null
  const defInclude = (r: ImportRow) => r.status === 'new'
  const included = (r: ImportRow) =>
    r.status !== 'error' && (includeOv[r.index] ?? defInclude(r))
  const origCat = (r: ImportRow) => r.category_id ?? defaultCat
  const catOf = (r: ImportRow) => catOv[r.index] ?? origCat(r)

  const selectedCount = preview.rows.filter(included).length
  const visible = preview.rows.filter((r) => filter === 'all' || r.status === filter)

  const handleError = (e: unknown) => {
    if (e instanceof ApiError && e.status === 404) onReset(pl.import.expired)
  }

  const submit = () => {
    const rows = preview.rows
      .filter(
        (r) =>
          r.status !== 'error' &&
          (included(r) !== defInclude(r) || catOv[r.index] !== undefined),
      )
      .map((r) => {
        const row: { index: number; include: boolean; category_id?: number | null } = {
          index: r.index,
          include: included(r),
        }
        if (catOv[r.index] !== undefined) row.category_id = catOv[r.index]
        return row
      })
    commit.mutate(
      { id: preview.id, rows },
      { onSuccess: onDone, onError: handleError },
    )
  }

  const doCancel = () =>
    cancel.mutate(preview.id, {
      onSuccess: () => onReset(),
      onError: (e) => (e instanceof ApiError && e.status === 404 ? onReset() : undefined),
    })

  const err = commit.error ?? cancel.error
  const filters: [Filter, string][] = [
    ['all', pl.import.filterAll],
    ['new', pl.import.filterNew],
    ['duplicate', pl.import.filterDuplicate],
    ['error', pl.import.filterError],
  ]

  return (
    <Card
      title={preview.filename}
      actions={
        <>
          <Badge tone="success">{pluralForm(preview.counts.new, pl.import.newCount)}</Badge>
          <Badge tone="warning">
            {pluralForm(preview.counts.duplicate, pl.import.duplicateCount)}
          </Badge>
          <Badge tone="danger">{pluralForm(preview.counts.error, pl.import.errorCount)}</Badge>
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="text-sm text-muted" htmlFor="import-filter">
          {pl.import.filter}
        </label>
        <Select
          id="import-filter"
          className="w-auto"
          value={filter}
          onChange={(e) => setFilter(e.target.value as Filter)}
        >
          {filters.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      {categories.isLoading && <Spinner />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="py-2 pr-3 font-medium">{pl.import.include}</th>
              <th className="py-2 pr-3 font-medium">{pl.import.date}</th>
              <th className="py-2 pr-3 font-medium">{pl.import.description}</th>
              <th className="py-2 pr-3 text-right font-medium">{pl.import.amount}</th>
              <th className="py-2 pr-3 font-medium">{pl.import.category}</th>
              <th className="py-2 font-medium">{pl.import.status}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.index} className="border-b border-border/60">
                <td className="py-2 pr-3">
                  <input
                    type="checkbox"
                    aria-label={pl.import.include}
                    checked={included(r)}
                    disabled={r.status === 'error'}
                    onChange={(e) =>
                      setIncludeOv((o) => ({ ...o, [r.index]: e.target.checked }))
                    }
                  />
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{r.date ?? ''}</td>
                <td className="py-2 pr-3">{r.description}</td>
                <td className="py-2 pr-3 text-right">
                  {r.amount !== null && <Money value={r.amount} colored />}
                </td>
                <td className="py-2 pr-3">
                  {r.status !== 'error' && (
                    <Select
                      aria-label={pl.import.category}
                      value={catOf(r) ?? ''}
                      onChange={(e) =>
                        setCatOv((o) => ({ ...o, [r.index]: Number(e.target.value) }))
                      }
                    >
                      {categories.data?.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </td>
                <td className="py-2">
                  <div className="flex flex-wrap items-center gap-1">
                    <Badge
                      tone={
                        r.status === 'new'
                          ? 'success'
                          : r.status === 'duplicate'
                            ? 'warning'
                            : 'danger'
                      }
                      className={r.error ? 'cursor-help' : undefined}
                    >
                      <span title={r.error ?? undefined}>
                        {r.status === 'new'
                          ? pl.import.statusNew
                          : r.status === 'duplicate'
                            ? pl.import.statusDuplicate
                            : pl.import.statusError}
                      </span>
                    </Badge>
                    {r.needs_review && catOv[r.index] === undefined && (
                      <Badge tone="info">{pl.import.needsReview}</Badge>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 space-y-2">
        <ErrorMessage message={err && !(err instanceof ApiError && err.status === 404) ? apiErrorMessage(err) : null} />
        <div className="flex gap-2">
          <Button onClick={submit} loading={commit.isPending} disabled={selectedCount === 0}>
            {commitButtonLabel(selectedCount)}
          </Button>
          <Button variant="secondary" onClick={doCancel} loading={cancel.isPending}>
            {pl.import.cancel}
          </Button>
        </div>
      </div>
    </Card>
  )
}

function ResultStep({
  result,
  onAnother,
  onFinished,
}: {
  result: CommitResult
  onAnother: () => void
  onFinished?: () => void
}) {
  const navigate = useNavigate()
  return (
    <Card>
      <p className="mb-4 rounded-md bg-accent-soft p-3 text-positive" role="status">
        {commitMessage(result)}
      </p>
      <div className="flex gap-2">
        <Button onClick={() => (onFinished ? onFinished() : navigate('/transactions'))}>{pl.import.viewTransactions}</Button>
        <Button variant="secondary" onClick={onAnother}>
          {pl.import.importAnother}
        </Button>
      </div>
    </Card>
  )
}
