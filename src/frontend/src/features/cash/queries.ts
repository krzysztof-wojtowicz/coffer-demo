import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/schema'
import { pl } from '../../i18n/pl'

export type OpeningBalance = components['schemas']['OpeningBalanceOut']

export const openingBalanceKey = ['opening-balance'] as const

export class OpeningBalanceError extends Error {}

function errorFrom(error: unknown, fallback: string): OpeningBalanceError {
  const d = (error as { detail?: unknown } | undefined)?.detail
  if (typeof d === 'string') return new OpeningBalanceError(d)
  if (Array.isArray(d)) {
    const msgs = d
      .map((x) => (x && typeof x === 'object' && 'msg' in x ? String((x as { msg: unknown }).msg) : ''))
      .filter(Boolean)
    if (msgs.length) return new OpeningBalanceError(msgs.join(' '))
  }
  return new OpeningBalanceError(fallback)
}

export function useOpeningBalance() {
  return useQuery({
    queryKey: openingBalanceKey,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/cash/opening-balance')
      if (error) throw errorFrom(error, pl.openingBalance.loadError)
      return (data ?? null) as OpeningBalance | null
    },
  })
}

function useInvalidate() {
  const qc = useQueryClient()
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: openingBalanceKey }),
      qc.invalidateQueries({ queryKey: ['net-worth'] }),
    ])
}

export function useSaveOpeningBalance() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (body: OpeningBalance) => {
      const { data, error } = await api.PUT('/api/cash/opening-balance', { body })
      if (error || !data) throw errorFrom(error, pl.openingBalance.saveError)
      return data
    },
    onSuccess: invalidate,
  })
}

export function useDeleteOpeningBalance() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/api/cash/opening-balance')
      if (error) throw errorFrom(error, pl.openingBalance.deleteError)
    },
    onSuccess: invalidate,
  })
}
