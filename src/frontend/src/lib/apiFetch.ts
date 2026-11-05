import { signOutLocally } from './queryClient'

/**
 * Plain fetch for calls that openapi-fetch handles poorly (multipart upload, SSE streams,
 * AbortController-heavy flows). Looks up globalThis.fetch per call, so test stubs work,
 * and applies the same 401 policy as the openapi-fetch middleware in api/client.ts.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const res = await globalThis.fetch(input, { credentials: 'include', ...init })
  if (res.status === 401 && !input.startsWith('/api/auth/')) signOutLocally()
  return res
}
