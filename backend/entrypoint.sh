#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres before touching the ORM. The db service also has a
# healthcheck, but this keeps `docker compose run` one-offs safe too.
# On Railway there is no POSTGRES_HOST — DATABASE_URL points at a managed
# instance that is already up, so this block is simply skipped.
if [ -n "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" -q; do
    sleep 1
  done
  echo "Postgres is up."
fi

# Media lives on a mounted volume in production; make sure it exists.
if [ -n "${DJANGO_MEDIA_ROOT:-}" ]; then
  mkdir -p "${DJANGO_MEDIA_ROOT}" || echo "Could not create ${DJANGO_MEDIA_ROOT}"
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
