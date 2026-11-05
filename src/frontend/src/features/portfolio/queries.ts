import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/schema'
import { pl } from '../../i18n/pl'

export type Holding = components['schemas']['HoldingOut']
export type HoldingCreate = components['schemas']['HoldingCreate']
export type HoldingUpdate = components['schemas']['HoldingUpdate']
export type PortfolioSummary = components['schemas']['PortfolioSummaryOut']
export type AssetClass = Holding['asset_class']

export const ASSET_CLASSES: AssetClass[] = [
  'stock',
  'etf',
  'bond',
  'real_estate',
  'commodity',
  'crypto',
  'cash',
]

export type AdviceHoldingIn = components['schemas']['HoldingIn']
export type AdviceRequest = components['schemas']['AdviceRequest']
export type InvestmentAdvice = components['schemas']['AdviceOut']
export type TopPick = components['schemas']['TopPickOut']
export type AdviceTip = components['schemas']['TipOut']

export function useHoldings() {
  return useQuery({
    queryKey: ['portfolio', 'holdings'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/portfolio/holdings')
      if (error) throw error
      return data
    },
  })
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['portfolio', 'summary'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/portfolio/summary')
      if (error) throw error
      return data
    },
  })
}

function useInvalidate() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: ['portfolio'] })
}

export function useCreateHolding() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (body: HoldingCreate) => {
      const { error } = await api.POST('/api/portfolio/holdings', { body })
      if (error) throw error
    },
    onSuccess: invalidate,
  })
}

export function useUpdateHolding() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: HoldingUpdate }) => {
      const { error } = await api.PATCH('/api/portfolio/holdings/{holding_id}', {
        params: { path: { holding_id: id } },
        body,
      })
      if (error) throw error
    },
    onSuccess: invalidate,
  })
}

export function useDeleteHolding() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE('/api/portfolio/holdings/{holding_id}', {
        params: { path: { holding_id: id } },
      })
      if (error) throw error
    },
    onSuccess: invalidate,
  })
}

export class AdviceError extends Error {}

export function useInvestmentAdvice() {
  return useMutation({
    mutationFn: async (holdings: AdviceHoldingIn[]): Promise<InvestmentAdvice> => {
      const body: AdviceRequest = { holdings }
      let result
      try {
        result = await api.POST('/api/agent/investment/advice', { body })
      } catch {
        throw new AdviceError(pl.portfolio.advisor.error)
      }
      const { data, error, response } = result
      if (response.status === 404 || response.status === 405) {
        throw new AdviceError(pl.portfolio.advisor.notAvailable)
      }
      if (error || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail
        throw new AdviceError(typeof detail === 'string' ? detail : pl.portfolio.advisor.error)
      }
      return data
    },
  })
}
