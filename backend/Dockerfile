# Multi-stage Dockerfile for the Kuwenta backend.
# Designed to run on Render (free tier, no persistent disk) with Neon Postgres.
# All runtime config comes from env vars — see render.yaml.

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

WORKDIR /app

# Install deps first (cached layer)
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# Copy source
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev


# ---- Runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# libpq is needed by psycopg2 at runtime (alembic uses it for migrations)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Receipts default to /tmp (ephemeral on Render free tier — wiped on cold starts).
# Override KUWENTA_RECEIPT_STORAGE_DIR to a real S3-mounted path for persistence.
RUN mkdir -p /tmp/receipts

EXPOSE 8000

# Render injects PORT — fall back to 8000 for local docker runs.
# Run migrations on startup; then exec uvicorn so signals propagate cleanly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
