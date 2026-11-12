import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export function useBudget(month: string) {
  return useQuery({
    queryKey: ['budget', month],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/budget/{month}', {
        params: { path: { month } },
      })
      if (error) throw error
      return data
    },
  })
}

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
