import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { pl } from '../../i18n/pl'
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

const FIELD_NAMES: Record<string, string> = {
  email: pl.auth.email,
  password: pl.auth.password,
  current_password: pl.auth.currentPassword,
  new_password: pl.auth.newPassword,
}

/**
 * Throw a UI error for a non-2xx response. Checks response.ok, not `error`: openapi-fetch
 * gives error=undefined/'' for an empty body (e.g. a proxy 429/503), which must not pass
 * as success. Validation lists are turned into Polish text with Polish field names.
 */
function fail(error: unknown, response: Response): never {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string' && detail) throw { detail }
  if (Array.isArray(detail)) {
    const text = detail
      .map((d: { loc?: (string | number)[]; type?: string }) => {
        const field = String(d.loc?.[d.loc.length - 1] ?? '')
        const name = FIELD_NAMES[field] ?? 'Pole'
        const what = d.type?.includes('missing') ? pl.validation.required : pl.validation.invalid
        return `${name}: ${what}`
      })
      .join('; ')
    throw { detail: text }
  }
  if (response.status === 429) throw { detail: pl.auth.tooManyAttempts }
  throw { detail: pl.common.genericError }
}

export function useAuth(mode: 'login' | 'register') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      // Register also logs in (the server sets the session cookie): no second request.
      const res =
        mode === 'login'
          ? await api.POST('/api/auth/login', { body })
          : await api.POST('/api/auth/register', { body })
      if (!res.response.ok) fail(res.error, res.response)
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

export function useChangePassword() {
  return useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) => {
      const res = await api.POST('/api/auth/password', { body })
      if (!res.response.ok) fail(res.error, res.response)
    },
  })
}

function useLeave(request: () => Promise<{ error?: unknown; response: Response }>) {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async () => {
      const res = await request()
      if (!res.response.ok) fail(res.error, res.response)
    },
    onSuccess: () => {
      signOutLocally()
      navigate('/login', { replace: true })
    },
  })
}

export function useLogoutAll() {
  return useLeave(() => api.POST('/api/auth/logout-all'))
}

export function useDeleteAccount(password: string) {
  return useLeave(() => api.DELETE('/api/auth/account', { body: { password } }))
}
