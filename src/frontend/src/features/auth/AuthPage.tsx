import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ErrorMessage } from '../../components/ErrorMessage'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { pl } from '../../i18n/pl'
import { apiErrorMessage } from '../../lib/errors'
import { NewPasswordField } from './PasswordField'
import { passwordProblems } from './password'
import { useAuth, useMe } from './queries'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const me = useMe()
  const auth = useAuth(mode)
  const navigate = useNavigate()
  const isLogin = mode === 'login'

  if (me.data) return <Navigate to="/" replace />

  const blocked = !isLogin && (passwordProblems(password, email).length > 0 || !consent)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (blocked) return
    auth.mutate({ email, password }, { onSuccess: () => navigate('/') })
  }
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm space-y-4">
        <p className="text-center text-3xl font-bold text-accent">{pl.appName}</p>
        <Card title={isLogin ? pl.auth.loginTitle : pl.auth.registerTitle}>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <Field label={pl.auth.email}>
              <Input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            {isLogin ? (
              <Field label={pl.auth.password}>
                <Input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
            ) : (
              <>
                <NewPasswordField
                  label={pl.auth.password}
                  value={password}
                  email={email}
                  onChange={setPassword}
                  showErrors={submitted}
                />
                <label className="flex items-start gap-2 text-sm text-text">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  {pl.auth.consent}
                </label>
                <ErrorMessage message={submitted && !consent ? pl.auth.consentRequired : null} />
              </>
            )}
            <ErrorMessage message={auth.error ? apiErrorMessage(auth.error) : null} />
            <Button type="submit" loading={auth.isPending}>
              {isLogin ? pl.auth.loginAction : pl.auth.registerAction}
            </Button>
          </form>
          <p className="mt-4 text-sm">
            <Link className="text-accent hover:underline" to={isLogin ? '/register' : '/login'}>
              {isLogin ? pl.auth.toRegister : pl.auth.toLogin}
            </Link>
          </p>
        </Card>
      </div>
    </main>
  )
}
