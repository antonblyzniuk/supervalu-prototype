#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres before touching the ORM.
#
# Compose has a healthcheck on the db service, but this also covers
# `docker compose run` one-offs and Railway, where DATABASE_URL points at the
# private domain — private networking needs a few seconds after boot, and
# without this the first migrate fails and the container restart-loops.
wait_for_postgres() {
  local attempts="${DB_WAIT_ATTEMPTS:-60}"
  local i=1

  while [ "$i" -le "$attempts" ]; do
    if [ -n "${POSTGRES_HOST:-}" ]; then
      pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" -q && return 0
    else
      pg_isready -d "${DATABASE_URL}" -q && return 0
    fi
    [ "$i" = 1 ] && echo "Waiting for Postgres..."
    i=$((i + 1))
    sleep 1
  done

  echo "Postgres did not become reachable after ${attempts}s." >&2
  return 1
}

if [ -n "${POSTGRES_HOST:-}" ] || [ -n "${DATABASE_URL:-}" ]; then
  wait_for_postgres
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
