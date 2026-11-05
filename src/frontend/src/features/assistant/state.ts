import type { components } from '../../api/schema'

export type SurplusResponse = components['schemas']['SurplusSuggestionOut']
export type Suggestion = components['schemas']['SuggestionOut']

export type AssistantState =
  | { status: 'idle' }
  | { status: 'loading'; steps: string[] }
  | { status: 'ok'; suggestion: Suggestion; runId: number | null }
  | { status: 'unavailable' }
  | { status: 'no_surplus' }
  | { status: 'limited' }

export type AssistantAction =
  | { type: 'start' }
  | { type: 'progress'; message: string }
  | { type: 'success'; response: SurplusResponse }
  | { type: 'failure' }
  | { type: 'cancel' }
  | { type: 'reset' }

export const initialAssistantState: AssistantState = { status: 'idle' }

export function assistantReducer(state: AssistantState, action: AssistantAction): AssistantState {
  switch (action.type) {
    case 'start':
      return { status: 'loading', steps: [] }
    case 'progress':
      if (state.status !== 'loading') return state
      return { status: 'loading', steps: [...state.steps, action.message] }
    case 'success': {
      const { ai_status, suggestion, run_id } = action.response
      if (ai_status === 'ok' && suggestion) {
        return { status: 'ok', suggestion, runId: run_id ?? null }
      }
      if (ai_status === 'no_surplus') return { status: 'no_surplus' }
      if (ai_status === 'limited') return { status: 'limited' }
      return { status: 'unavailable' }
    }
    case 'failure':
      return { status: 'unavailable' }
    case 'cancel':
    case 'reset':
      return { status: 'idle' }
    default:
      return state
  }
}
