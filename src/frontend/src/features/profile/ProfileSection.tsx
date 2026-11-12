import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { ProfileError, useProfile, useSaveProfile, type ProfileIn, type ProfileOut } from './queries'

const HORIZONS = ['short', 'medium', 'long'] as const
const RISKS = ['low', 'medium', 'high'] as const
const CLASSES = ['cash', 'deposit', 'stocks', 'etf', 'bonds', 'crypto', 'real_estate'] as const

type Bucket = 'safe' | 'bonds' | 'equity' | 'alternative'

// Illustrative, static allocation per risk level (percent). Not advice; UI-only.
const ALLOCATION: Record<ProfileIn['risk'], [Bucket, number][]> = {
  low: [
    ['safe', 40],
    ['bonds', 45],
    ['equity', 15],
  ],
  medium: [
    ['safe', 15],
    ['bonds', 35],
    ['equity', 45],
    ['alternative', 5],
  ],
  high: [
    ['safe', 5],
    ['bonds', 15],
    ['equity', 65],
    ['alternative', 15],
  ],
}
const BUCKET_COLOR: Record<Bucket, string> = {
  safe: 'bg-text',
  bonds: 'bg-info',
  equity: 'bg-accent',
  alternative: 'bg-positive',
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })

export function ProfileSection() {
  const p = pl.profile
  const profile = useProfile()
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)

  if (profile.isPending) {
    return (
      <Card title={p.title}>
        <Spinner className="size-5" />
      </Card>
    )
  }
  if (profile.isError) {
    return (
      <Card title={p.title}>
        <ErrorMessage message={p.loadError} />
      </Card>
    )
  }

  const data = profile.data
  const onSaved = () => {
    setEditing(false)
    setSaved(true)
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <Card title={p.title}>
          <h3 className="text-lg font-semibold">{p.emptyTitle}</h3>
          <p className="mt-1 text-sm text-muted">{p.emptyText}</p>
        </Card>
        <Card>
          <ProfileForm onSaved={onSaved} />
        </Card>
      </div>
    )
  }

  if (editing) {
    return (
      <Card title={p.title}>
        <ProfileForm initial={data} onSaved={onSaved} onCancel={() => setEditing(false)} />
      </Card>
    )
  }

  return (
    <ProfileSummary
      profile={data}
      saved={saved}
      onEdit={() => {
        setSaved(false)
        setEditing(true)
      }}
    />
  )
}

function ProfileSummary({
  profile,
  saved,
  onEdit,
}: {
  profile: ProfileOut
  saved: boolean
  onEdit: () => void
}) {
  const p = pl.profile
  const level = RISKS.indexOf(profile.risk) + 1
  const allocation = ALLOCATION[profile.risk]

  return (
    <div className="space-y-4">
      <Card
        title={p.title}
        actions={
          <Button variant="secondary" size="sm" onClick={onEdit}>
            {p.edit}
          </Button>
        }
      >
        {saved && (
          <p role="status" className="mb-3 text-sm text-positive">
            {p.saved}
          </p>
        )}
        <p className="text-xs uppercase tracking-wide text-muted">{p.yourProfile}</p>
        <h3 className="text-2xl font-semibold">{p.profileName[profile.risk]}</h3>
        <p className="mt-1 text-sm text-muted">{p.profileDesc[profile.risk]}</p>

        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium">{p.riskScale}</span>
            <span>{p.risk[profile.risk]}</span>
          </div>
          <div
            role="meter"
            aria-label={p.riskScale}
            aria-valuemin={1}
            aria-valuemax={3}
            aria-valuenow={level}
            aria-valuetext={p.risk[profile.risk]}
            className="flex gap-1"
          >
            {RISKS.map((r, i) => (
              <div
                key={r}
                className={cn(
                  'h-2 flex-1 rounded-full',
                  i < level ? (level === 3 ? 'bg-warning' : 'bg-accent') : 'bg-surface-2',
                )}
              />
            ))}
          </div>
          <div className="mt-1 flex justify-between text-xs text-muted">
            <span>{p.riskScaleLow}</span>
            <span>{p.riskScaleHigh}</span>
          </div>
        </div>

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">{p.horizonLabel}</dt>
            <dd className="font-medium">{p.horizon[profile.horizon]}</dd>
          </div>
          <div>
            <dt className="text-muted">{p.updatedAt}</dt>
            <dd className="font-medium">{formatDate(profile.updated_at)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="mb-1 text-muted">{p.classesLabel}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {CLASSES.filter((c) => profile.preferred_classes.includes(c)).map((c) => (
                <Badge key={c}>{p.classes[c]}</Badge>
              ))}
            </dd>
          </div>
        </dl>
      </Card>

      <Card
        title={p.allocationTitle}
        actions={
          <Link className="text-sm text-accent hover:underline" to="/portfolio">
            {p.seePortfolio}
          </Link>
        }
      >
        <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
          {allocation.map(([b, pct]) => (
            <div key={b} className={BUCKET_COLOR[b]} style={{ width: `${pct}%` }} />
          ))}
        </div>
        <ul className="mt-3 space-y-1 text-sm">
          {allocation.map(([b, pct]) => (
            <li key={b} className="flex items-center gap-2">
              <span className={cn('size-2.5 rounded-sm', BUCKET_COLOR[b])} aria-hidden="true" />
              <span className="flex-1">{p.allocationClasses[b]}</span>
              <span className="tabular-nums font-medium">{pct}%</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">{p.allocationNote}</p>
      </Card>
    </div>
  )
}

function ProfileForm({
  initial,
  onSaved,
  onCancel,
}: {
  initial?: ProfileOut
  onSaved: () => void
  onCancel?: () => void
}) {
  const p = pl.profile
  const save = useSaveProfile()
  const [horizon, setHorizon] = useState<ProfileIn['horizon']>(initial?.horizon ?? 'medium')
  const [risk, setRisk] = useState<ProfileIn['risk']>(initial?.risk ?? 'medium')
  const [classes, setClasses] = useState<ProfileIn['preferred_classes']>(initial?.preferred_classes ?? [])

  const toggle = (c: (typeof CLASSES)[number]) =>
    setClasses((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { horizon, risk, preferred_classes: CLASSES.filter((c) => classes.includes(c)) },
      { onSuccess: onSaved },
    )
  }

  const errors =
    save.error instanceof ProfileError && save.error.messages.length > 0
      ? save.error.messages
      : save.error
        ? [p.saveError]
        : []

  return (
    <form onSubmit={submit} className="space-y-5">
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">{p.horizonLabel}</legend>
        {HORIZONS.map((h) => (
          <label key={h} className="flex items-center gap-2 text-sm">
            <input type="radio" name="horizon" checked={horizon === h} onChange={() => setHorizon(h)} />
            {p.horizon[h]}
          </label>
        ))}
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">{p.riskLabel}</legend>
        {RISKS.map((r) => (
          <label key={r} className="flex items-start gap-2 text-sm">
            <input type="radio" name="risk" className="mt-1" checked={risk === r} onChange={() => setRisk(r)} />
            <span>
              {p.risk[r]}
              <span className="block text-muted">{p.riskDesc[r]}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">{p.classesLabel}</legend>
        {CLASSES.map((c) => (
          <label key={c} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={classes.includes(c)} onChange={() => toggle(c)} />
            {p.classes[c]}
          </label>
        ))}
        <p className="text-xs text-muted">{p.classesHint}</p>
      </fieldset>
      <p className="text-sm text-muted">{p.note}</p>
      {errors.map((m) => (
        <ErrorMessage key={m} message={m} />
      ))}
      <div className="flex gap-2">
        <Button type="submit" disabled={classes.length === 0} loading={save.isPending}>
          {p.save}
        </Button>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={save.isPending}>
            {p.cancel}
          </Button>
        )}
      </div>
    </form>
  )
}
