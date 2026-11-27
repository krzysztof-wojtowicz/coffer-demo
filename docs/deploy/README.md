# Deployment

Production runs on three free plans:

```
browser ──► Vercel (SPA, rewrite /api/*) ──► Render (FastAPI, Docker, Frankfurt) ──► Neon (Postgres, Frankfurt)
```

The browser sees only the Vercel domain, so the `SameSite=Lax` session cookie works without CORS. Local development is in [development.md](../development.md); the deployment diagram is in [architecture.md §3](../architecture.md#3-deployment).

| Doc | What |
|---|---|
| [database.md](database.md) | Neon: setup, direct vs pooled URL, remote migrations, backup, reset |
| [backend.md](backend.md) | Render: environment, LLM in production, price job, Origin/CORS, deploy hook |
| [frontend.md](frontend.md) | Vercel: rewrites, SSE limits, security headers |
| [ci.md](ci.md) | GitHub Actions workflows, Dependabot, branch protection |
| [release-checklist.md](release-checklist.md) | Steps for a release with migrations, smoke tests, rollback |
