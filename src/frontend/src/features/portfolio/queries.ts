import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/schema'

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
  return () => {
    qc.invalidateQueries({ queryKey: ['net-worth'] })
    return qc.invalidateQueries({ queryKey: ['portfolio'] })
  }
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

/** Deep link to the assistant's purchase-impact action (see E5-06). */
export function purchaseImpactLink(assetClass?: string, symbol?: string | null): string {
  const p = new URLSearchParams({ action: 'purchase_impact' })
  if (assetClass) p.set('asset_class', assetClass)
  if (symbol) p.set('symbol', symbol)
  return `/assistant?${p.toString()}`
}

export function formatAsOf(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** True when a quote is older than 24 h. */
export function isStale(iso: string | null | undefined, now: number = Date.now()): boolean {
  return !!iso && now - new Date(iso).getTime() > 24 * 3600 * 1000
}
