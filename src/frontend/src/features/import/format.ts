import { pl } from '../../i18n/pl'

type Forms = readonly string[]

const rules = new Intl.PluralRules('pl-PL')

/** Wybiera polską formę (1 / 2-4 / reszta) z szablonu z `{n}` lub zwykłego słowa. */
export function pluralForm(n: number, forms: Forms): string {
  const cat = rules.select(n)
  const form = cat === 'one' ? forms[0] : cat === 'few' ? forms[1] : forms[2]
  return form.replace('{n}', String(n))
}

const withNumber = (n: number, forms: Forms) => `${n} ${pluralForm(n, forms)}`

const imp = () => pl.import

/** "Zaimportowano 17 transakcji, pominięto 1 duplikat i 1 błąd". */
export function commitMessage(r: {
  imported: number
  skipped_duplicates: number
  skipped_errors: number
}): string {
  const t = imp()
  let msg = `${t.imported} ${withNumber(r.imported, t.transactionsAcc)}`
  const skipped: string[] = []
  if (r.skipped_duplicates > 0) {
    skipped.push(pluralForm(r.skipped_duplicates, t.duplicateCount))
  }
  if (r.skipped_errors > 0) skipped.push(pluralForm(r.skipped_errors, t.errorCount))
  if (skipped.length > 0) msg += `, ${t.skipped} ${skipped.join(` ${t.and} `)}`
  return msg
}

export function commitButtonLabel(n: number): string {
  return `${pl.import.commit.replace('{n}', String(n))} ${pluralForm(n, pl.import.transactionsAcc)}`
}

