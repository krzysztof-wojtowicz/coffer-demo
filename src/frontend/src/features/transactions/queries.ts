import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/categories')
      if (error) throw error
      return data
    },
  })
}

export function useTransactions(month: string) {
  return useQuery({
    queryKey: ['transactions', month],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/transactions', {
        params: { query: { month } },
      })
      if (error) throw error
      return data
    },
  })
}

function useInvalidate() {
  const qc = useQueryClient()
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['transactions'] }),
      qc.invalidateQueries({ queryKey: ['budget'] }),
    ])
}

export function useCreateTransaction() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (body: {
      date: string
      amount: string
      description: string
      category_id: number | null
    }) => {
      const { error } = await api.POST('/api/transactions', { body })
      if (error) throw error
    },
    onSuccess: invalidate,
  })
}

export function useDeleteTransaction() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE('/api/transactions/{transaction_id}', {
        params: { path: { transaction_id: id } },
      })
      if (error) throw error
    },
    onSuccess: invalidate,
  })
}
