import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient()

/**
 * Forget the logged-in user and all their cached data. The route guard observes the
 * ['me'] query, so setting it to null redirects to /login. We must not call
 * queryClient.clear() here: it would detach the guard's observer from the cache.
 */
export function signOutLocally(): void {
  queryClient.setQueryData(['me'], null)
  queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
}
