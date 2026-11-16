import { pl } from '../../i18n/pl'
import { ActionPanel } from './ActionPanel'
import { RunsTable } from './RunsTable'
import { SuggestionHistory } from './SuggestionHistory'

export function AssistantPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-text">{pl.nav.assistant}</h1>
      <ActionPanel />
      <SuggestionHistory />
      <RunsTable />
    </div>
  )
}
