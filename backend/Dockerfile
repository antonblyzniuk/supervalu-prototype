# syntax=docker/dockerfile:1

# --------------------------------------------------------------------------
# Base — shared runtime layer
# --------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./

# --------------------------------------------------------------------------
# Development — extra tooling, autoreloading runserver
# --------------------------------------------------------------------------
FROM base AS dev

RUN pip install -r requirements-dev.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --------------------------------------------------------------------------
# Production — runtime deps only, gunicorn, non-root
# --------------------------------------------------------------------------
FROM base AS prod

RUN pip install -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app

USER appuser

# Static files are baked in at build time so a cold start is just gunicorn.
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

ENTRYPOINT ["/app/entrypoint.sh"]
# Shell form: Railway assigns $PORT at runtime, so it cannot be baked in.
CMD ["sh", "-c", "gunicorn config.wsgi:application \
     --bind 0.0.0.0:${PORT:-8000} \
     --workers ${WEB_CONCURRENCY:-3} \
     --timeout 60 \
     --access-logfile - \
     --error-logfile -"]
