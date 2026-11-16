import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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

export function useInsights(month: string) {
  return useQuery({
    queryKey: ['budget', 'insights', month],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/budget/{month}/insights', {
        params: { path: { month } },
      })
      if (error) throw error
      return data
    },
  })
}

export function useLimits() {
  return useQuery({
    queryKey: ['budget', 'limits'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/budget/limits')
      if (error) throw error
      return data
    },
  })
}

function useRefreshBudget() {
  const qc = useQueryClient()
  return () => Promise.all([
    qc.invalidateQueries({ queryKey: ['budget', 'limits'] }),
    qc.invalidateQueries({ queryKey: ['budget', 'insights'] }),
  ])
}

export function useSetLimit() {
  const refresh = useRefreshBudget()
  return useMutation({
    mutationFn: async ({ categoryId, amount }: { categoryId: number; amount: string }) => {
      const { data, error } = await api.PUT('/api/budget/limits/{category_id}', {
        params: { path: { category_id: categoryId } },
        body: { amount },
      })
      if (error) throw error
      return data
    },
    onSuccess: refresh,
  })
}

export function useDeleteLimit() {
  const refresh = useRefreshBudget()
  return useMutation({
    mutationFn: async (categoryId: number) => {
      const { error } = await api.DELETE('/api/budget/limits/{category_id}', {
        params: { path: { category_id: categoryId } },
      })
      if (error) throw error
    },
    onSuccess: refresh,
  })
}
