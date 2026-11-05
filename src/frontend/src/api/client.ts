import createClient from 'openapi-fetch'
import { signOutLocally } from '../lib/queryClient'
import type { paths } from './schema'

export const api = createClient<paths>({ baseUrl: '/', credentials: 'include' })

// Session expired or revoked while the app is open: treat any 401 outside the auth
// endpoints as "logged out", so the user lands on the login page instead of a dead UI.
api.use({
  onResponse({ request, response }) {
    if (response.status === 401 && !new URL(request.url).pathname.startsWith('/api/auth/')) {
      signOutLocally()
    }
    return response
  },
})
