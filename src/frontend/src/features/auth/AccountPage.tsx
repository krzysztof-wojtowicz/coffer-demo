import { useState, type FormEvent } from 'react'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { NewPasswordField } from './PasswordField'
import { passwordProblems } from './password'
import { useChangePassword, useDeleteAccount, useLogoutAll, useMe } from './queries'

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
    <Card title={pl.auth.changePasswordTitle}>
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
    </Card>
  )
}

function Sessions() {
  const logoutAll = useLogoutAll()
  return (
    <Card title={pl.auth.sessionsTitle}>
      <p className="mb-3 text-sm text-muted">{pl.auth.sessionsHint}</p>
      <ErrorMessage message={logoutAll.error ? apiErrorMessage(logoutAll.error) : null} />
      <Button variant="secondary" loading={logoutAll.isPending} onClick={() => logoutAll.mutate()}>
        {pl.auth.logoutAllAction}
      </Button>
    </Card>
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
    <Card title={pl.auth.deleteTitle}>
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
    </Card>
  )
}

export function AccountPage() {
  const me = useMe()
  const email = me.data?.email ?? ''
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{pl.auth.accountTitle}</h1>
      <ChangePassword email={email} />
      <Sessions />
      <DeleteAccount />
    </div>
  )
}
