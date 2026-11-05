import { apiFetch } from '../../lib/apiFetch'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/schema'

export type ImportPreview = components['schemas']['ImportPreviewOut']
export type ImportRow = components['schemas']['ImportRowOut']
export type CommitRow = components['schemas']['CommitRow']
export type CommitResult = components['schemas']['CommitOut']

/** Błąd z kodem HTTP i ciałem API (kompatybilny z apiErrorMessage). */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : 'API error')
    this.status = status
    this.detail = detail
  }
}

export function useBanks() {
  return useQuery({
    queryKey: ['import-banks'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/imports/banks')
      if (error) throw error
      return data
    },
  })
}

export function useUpload() {
  return useMutation({
    mutationFn: async ({ file, bank }: { file: File; bank: string }) => {
      const form = new FormData()
      form.append('file', file)
      form.append('bank', bank)
      const res = await apiFetch('/api/imports', {
        method: 'POST',
        body: form,
        credentials: 'include',
      })
      const body: unknown = await res.json().catch(() => undefined)
      if (!res.ok) throw new ApiError(res.status, (body as { detail?: unknown })?.detail)
      return body as ImportPreview
    },
  })
}

export function useCommit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, rows }: { id: string; rows: CommitRow[] }) => {
      const { data, error, response } = await api.POST('/api/imports/{draft_id}/commit', {
        params: { path: { draft_id: id } },
        body: { rows },
      })
      if (error) throw new ApiError(response.status, (error as { detail?: unknown }).detail)
      return data
    },
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ['transactions'] }),
        qc.invalidateQueries({ queryKey: ['budget'] }),
      ]),
  })
}

export function useCancel() {
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE('/api/imports/{draft_id}', {
        params: { path: { draft_id: id } },
      })
      if (error) throw new ApiError(response.status, (error as { detail?: unknown }).detail)
    },
  })
}
