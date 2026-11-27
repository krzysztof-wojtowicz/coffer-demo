import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { AllocationChart, targetSlices } from '../portfolio/AllocationChart'
import { ASSET_CLASSES } from '../portfolio/queries'
import { ProfileError, useProfile, useSaveProfile, type ProfileIn, type ProfileOut } from './queries'

const HORIZONS = ['short', 'medium', 'long'] as const
const RISKS = ['low', 'medium', 'high'] as const

const chip = (on: boolean) =>
  cn(
    'rounded px-3 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
    on ? 'bg-accent-soft font-semibold text-accent' : 'text-muted hover:bg-surface-2 hover:text-text',
  )

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-md bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={chip(value === o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

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
  return (
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
      <dl className="mb-5 flex flex-wrap gap-x-8 gap-y-3 text-sm">
        <div>
          <dt className="text-muted">{p.horizonLabel}</dt>
          <dd className="font-medium">{p.horizon[profile.horizon]}</dd>
        </div>
        <div>
          <dt className="text-muted">{p.riskLabel}</dt>
          <dd className="font-medium">{p.risk[profile.risk]}</dd>
        </div>
      </dl>
      <h3 className="mb-3 text-sm font-medium text-muted">{p.targetTitle}</h3>
      <AllocationChart
        compact
        allocation={targetSlices(profile.target.map((t) => ({ asset_class: t.asset_class, share_pct: t.share_pct })))}
      />
      <p className="mt-4 text-xs text-muted">{p.allocationNote}</p>
    </Card>
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

  const toggle = (c: ProfileIn['preferred_classes'][number]) =>
    setClasses((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { horizon, risk, preferred_classes: ASSET_CLASSES.filter((c) => classes.includes(c)) },
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
      <div className="space-y-2">
        <p className="text-sm font-medium">{p.horizonLabel}</p>
        <Segmented
          label={p.horizonLabel}
          value={horizon}
          onChange={setHorizon}
          options={HORIZONS.map((h) => ({ value: h, label: p.horizon[h] }))}
        />
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium">{p.riskLabel}</p>
        <Segmented
          label={p.riskLabel}
          value={risk}
          onChange={setRisk}
          options={RISKS.map((r) => ({ value: r, label: p.risk[r] }))}
        />
        <p className="text-sm text-muted">{p.riskDesc[risk]}</p>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium">{p.classesLabel}</p>
        <div role="group" aria-label={p.classesLabel} className="flex flex-wrap gap-2">
          {ASSET_CLASSES.map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={classes.includes(c)}
              onClick={() => toggle(c)}
              className={cn(chip(classes.includes(c)), 'bg-surface-2')}
            >
              {pl.assetClass[c]}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted">{p.classesHint}</p>
      </div>
      {errors.map((m) => (
        <ErrorMessage key={m} message={m} />
      ))}
      <div className="flex gap-2 border-t border-border pt-4">
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
