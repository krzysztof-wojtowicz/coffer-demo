import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { pl } from '../../i18n/pl'
import { OpeningBalanceSection } from '../cash/OpeningBalanceSection'
import { useOpeningBalance } from '../cash/queries'
import { formatMoney } from '../../lib/format'
import { SettingsRow } from './SettingsRow'
import { ProfileSection } from '../profile/ProfileSection'
import { apiErrorMessage } from '../../lib/errors'
import { NewPasswordField } from './PasswordField'
import { passwordProblems } from './password'
import { useChangePassword, useDeleteAccount, useLogoutAll, useMe, useUpdateName } from './queries'

function ChangePassword({ email }: { email: string }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const change = useChangePassword()
  const sameAsCurrent = next !== '' && next === current

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (passwordProblems(next, email).length > 0 || sameAsCurrent) return
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent('')
          setNext('')
          setSubmitted(false)
        },
      },
    )
  }
  return (
    <>
      <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
        <Field label={pl.auth.currentPassword}>
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </Field>
        <NewPasswordField
          label={pl.auth.newPassword}
          value={next}
          email={email}
          onChange={setNext}
          showErrors={submitted}
        />
        <ErrorMessage message={submitted && sameAsCurrent ? pl.auth.sameAsCurrent : null} />
        <ErrorMessage message={change.error ? apiErrorMessage(change.error) : null} />
        {change.isSuccess && (
          <p className="text-sm text-positive" role="status">
            {pl.auth.passwordChanged}
          </p>
        )}
        <Button type="submit" loading={change.isPending}>
          {pl.auth.changePasswordAction}
        </Button>
      </form>
    </>
  )
}

function ChangeName({ current }: { current: string }) {
  const [name, setName] = useState(current)
  const [error, setError] = useState<string | null>(null)
  const update = useUpdateName()
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length < 1 || trimmed.length > 50) {
      setError(pl.auth.nameInvalid)
      return
    }
    setError(null)
    update.mutate(trimmed)
  }
  return (
    <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
      <Field label={pl.auth.displayName}>
        <Input required maxLength={50} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <ErrorMessage message={error ?? (update.error ? apiErrorMessage(update.error) : null)} />
      {update.isSuccess && (
        <p className="text-sm text-positive" role="status">
          {pl.auth.nameChanged}
        </p>
      )}
      <div>
        <Button type="submit" loading={update.isPending}>
          {pl.auth.saveName}
        </Button>
      </div>
    </form>
  )
}

function Sessions() {
  const logoutAll = useLogoutAll()
  return (
    <>
      <p className="mb-3 text-sm text-muted">{pl.auth.sessionsHint}</p>
      <ErrorMessage message={logoutAll.error ? apiErrorMessage(logoutAll.error) : null} />
      <Button variant="secondary" loading={logoutAll.isPending} onClick={() => logoutAll.mutate()}>
        {pl.auth.logoutAllAction}
      </Button>
    </>
  )
}

function DeleteAccount() {
  const [password, setPassword] = useState('')
  const remove = useDeleteAccount(password)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    remove.mutate()
  }
  return (
    <>
      <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
        <p className="text-sm text-negative">{pl.auth.deleteWarning}</p>
        <Field label={pl.auth.deleteConfirmLabel}>
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <ErrorMessage message={remove.error ? apiErrorMessage(remove.error) : null} />
        <Button type="submit" variant="danger" loading={remove.isPending}>
          {pl.auth.deleteAction}
        </Button>
      </form>
    </>
  )
}

type Row = 'name' | 'password' | 'balance' | 'sessions' | 'delete'

export function AccountPage() {
  const me = useMe()
  const balance = useOpeningBalance()
  // One row open at a time.
  const [open, setOpen] = useState<Row | null>(null)
  const email = me.data?.email ?? ''
  const name = me.data?.display_name ?? ''
  const row = (r: Row) => ({ open: open === r, onToggle: () => setOpen((cur) => (cur === r ? null : r)) })
  return (
    <div className="space-y-4">
      <h1 className="sr-only">{pl.auth.accountTitle}</h1>
      <ProfileSection />
      <Card title={pl.auth.settingsTitle}>
        <SettingsRow label={pl.auth.displayName} value={name} {...row('name')}>
          <ChangeName key={name} current={name} />
        </SettingsRow>
        <SettingsRow label={pl.auth.password} value="••••••••" {...row('password')}>
          <ChangePassword email={email} />
        </SettingsRow>
        <SettingsRow
          label={pl.auth.openingBalanceRow}
          value={
            balance.data
              ? `${formatMoney(balance.data.amount)} (${balance.data.as_of})`
              : pl.auth.notSet
          }
          {...row('balance')}
        >
          <OpeningBalanceSection />
        </SettingsRow>
        <SettingsRow label={pl.auth.sessionsTitle} value={pl.auth.logoutAllAction} {...row('sessions')}>
          <Sessions />
        </SettingsRow>
        <SettingsRow label={pl.auth.deleteTitle} danger {...row('delete')}>
          <DeleteAccount />
        </SettingsRow>
      </Card>
    </div>
  )
}
