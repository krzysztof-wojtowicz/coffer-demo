import { apiFetch } from '../../lib/apiFetch'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from '../../api/schema'

export type ProfileIn = components['schemas']['ProfileIn']

export class ProfileError extends Error {
  messages: string[]
  constructor(messages: string[]) {
    super(messages.join(' '))
    this.messages = messages
  }
}

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const res = await apiFetch('/api/profile', { credentials: 'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return (await res.json()) as components['schemas']['ProfileOut'] | null
    },
  })
}

function detailMessages(detail: unknown): string[] {
  if (typeof detail === 'string') return [detail]
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
      .filter(Boolean)
  }
  return []
}

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ProfileIn) => {
      const res = await apiFetch('/api/profile', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: unknown }
        throw new ProfileError(detailMessages(err.detail))
      }
      return (await res.json()) as components['schemas']['ProfileOut']
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })
}
