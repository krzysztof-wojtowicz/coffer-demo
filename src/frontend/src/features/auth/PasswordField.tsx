import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { pl } from '../../i18n/pl'
import { cn } from '../../lib/cn'
import { passwordProblems, passwordStrength } from './password'

const barColors = ['bg-negative', 'bg-negative', 'bg-warning', 'bg-info', 'bg-positive']

/** New-password input with live policy check and a strength meter. */
export function NewPasswordField({
  label,
  value,
  email,
  onChange,
  showErrors,
}: {
  label: string
  value: string
  email: string
  onChange: (v: string) => void
  showErrors: boolean
}) {
  const problems = passwordProblems(value, email)
  const score = passwordStrength(value, email)
  return (
    <div className="flex flex-col gap-1">
      <Field label={label}>
        <Input
          type="password"
          autoComplete="new-password"
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={showErrors && problems.length > 0}
        />
      </Field>
      <div className="flex items-center gap-2" aria-live="polite">
        <div
          className="flex h-1.5 flex-1 gap-1"
          role="meter"
          aria-label={pl.auth.strength}
          aria-valuemin={0}
          aria-valuemax={4}
          aria-valuenow={score}
          aria-valuetext={pl.auth.strengthLabels[score]}
        >
          {[1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className={cn('flex-1 rounded-full', i <= score ? barColors[score] : 'bg-border')}
            />
          ))}
        </div>
        <span className="text-xs font-normal text-muted">
          {value ? pl.auth.strengthLabels[score] : ''}
        </span>
      </div>
      {value && problems.length > 0 && (
        <div className="text-xs font-normal">
          <p className="text-muted">{pl.auth.rulesTitle}</p>
          <ul
            className={cn('list-disc pl-4', showErrors ? 'text-negative' : 'text-muted')}
            role={showErrors ? 'alert' : undefined}
          >
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
