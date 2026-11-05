import { useEffect, useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { pl } from '../../i18n/pl'
import { ProfileError, useProfile, useSaveProfile, type ProfileIn } from './queries'

const HORIZONS = ['short', 'medium', 'long'] as const
const RISKS = ['low', 'medium', 'high'] as const
const CLASSES = ['cash', 'deposit', 'stocks', 'etf', 'bonds', 'crypto', 'real_estate'] as const

export function ProfilePage() {
  const p = pl.profile
  const profile = useProfile()
  const save = useSaveProfile()
  const [horizon, setHorizon] = useState<ProfileIn['horizon']>('medium')
  const [risk, setRisk] = useState<ProfileIn['risk']>('medium')
  const [classes, setClasses] = useState<ProfileIn['preferred_classes']>([])
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (profile.data) {
      setHorizon(profile.data.horizon)
      setRisk(profile.data.risk)
      setClasses(profile.data.preferred_classes)
    }
  }, [profile.data])

  const toggle = (c: (typeof CLASSES)[number]) => {
    setSaved(false)
    setClasses((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]))
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSaved(false)
    save.mutate(
      { horizon, risk, preferred_classes: CLASSES.filter((c) => classes.includes(c)) },
      { onSuccess: () => setSaved(true) },
    )
  }

  const errors =
    save.error instanceof ProfileError && save.error.messages.length > 0
      ? save.error.messages
      : save.error
        ? [p.saveError]
        : []

  return (
    <Card title={p.title}>
      <form onSubmit={submit} className="space-y-5">
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">{p.horizonLabel}</legend>
          {HORIZONS.map((h) => (
            <label key={h} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="horizon"
                checked={horizon === h}
                onChange={() => {
                  setHorizon(h)
                  setSaved(false)
                }}
              />
              {p.horizon[h]}
            </label>
          ))}
        </fieldset>
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">{p.riskLabel}</legend>
          {RISKS.map((r) => (
            <label key={r} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="risk"
                className="mt-1"
                checked={risk === r}
                onChange={() => {
                  setRisk(r)
                  setSaved(false)
                }}
              />
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
        {saved && (
          <p role="status" className="text-sm text-positive">
            {p.saved}
          </p>
        )}
        <Button type="submit" disabled={classes.length === 0} loading={save.isPending}>
          {p.save}
        </Button>
      </form>
    </Card>
  )
}
