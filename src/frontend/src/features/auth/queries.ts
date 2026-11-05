import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { signOutLocally } from '../../lib/queryClient'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    retry: false,
    queryFn: async () => {
      const { data, response } = await api.GET('/api/auth/me')
      if (response.status === 401) return null
      return data ?? null
    },
  })
}

export function useAuth(mode: 'login' | 'register') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      const res =
        mode === 'login'
          ? await api.POST('/api/auth/login', { body })
          : await api.POST('/api/auth/register', { body })
      if (res.error) throw res.error
      if (mode === 'register') {
        const r = await api.POST('/api/auth/login', { body })
        if (r.error) throw r.error
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['me'] }),
  })
}

export function useLogout() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => api.POST('/api/auth/logout'),
    // onSettled: even if the request fails, the user asked to leave, so drop local state.
    onSettled: () => {
      signOutLocally()
      navigate('/login', { replace: true })
    },
  })
}
