# Coffer API: production image (Render Web Service, free plan).
# Build context: src/backend
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

# The app expects the repo layout (config.py looks for .env four levels up),
# so the code lives in /app/src/backend. No .env is copied: config comes from env vars.
WORKDIR /app/src/backend

# Dependencies first (cached layer): only the lockfile, no dev group, no project yet.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY coffer ./coffer
RUN uv sync --frozen --no-dev --no-editable

RUN useradd --create-home --uid 10001 coffer && chown -R coffer:coffer /app
USER coffer

ENV PATH="/opt/venv/bin:$PATH" \
    PORT=8000
EXPOSE 8000

# Render injects PORT; TLS ends at Render's proxy, so trust X-Forwarded-* headers.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn coffer.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
