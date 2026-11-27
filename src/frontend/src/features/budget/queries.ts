import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export function useNetWorth() {
  return useQuery({
    queryKey: ['net-worth'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/budget/net-worth')
      if (error) throw error
      return data
    },
  })
}

export function useTrend(month: string, months: number) {
  return useQuery({
    queryKey: ['budget', 'trend', month, months],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/budget/{month}/trend', {
        params: { path: { month }, query: { months: months as 3 | 6 | 12 } },
      })
      if (error) throw error
      return data
    },
  })
}

export type Trend = NonNullable<ReturnType<typeof useTrend>['data']>
