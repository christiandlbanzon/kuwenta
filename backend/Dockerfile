# Multi-stage Dockerfile for the Kuwenta backend.
# Stage 1: install deps with uv into a /app/.venv
# Stage 2: minimal runtime image with the venv + source

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv is the single dep we need to bootstrap; everything else comes via uv sync
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

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Persistent volume for SQLite + receipts (mounted at /data on Fly.io)
RUN mkdir -p /data /data/receipts
ENV KUWENTA_DATABASE_URL="sqlite+aiosqlite:////data/kuwenta.db" \
    KUWENTA_RECEIPT_STORAGE_DIR="/data/receipts"

EXPOSE 8000

# Run migrations on startup, then start uvicorn.
# In production we'd want a separate migration step, but for a v1 free-tier deploy
# this is the simplest "it just works" approach.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
