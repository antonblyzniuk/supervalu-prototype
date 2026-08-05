#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-appuser}"
FALLBACK_MEDIA_ROOT="/app/media"

have_app_user() {
  id "$APP_USER" >/dev/null 2>&1
}

running_as_root() {
  [ "$(id -u)" = "0" ]
}

# Can the account that will actually serve requests write here?
writable_by_app_user() {
  local dir="$1"
  if running_as_root && have_app_user; then
    su -s /bin/sh "$APP_USER" -c "test -w '$dir'"
  else
    test -w "$dir"
  fi
}

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

# Signatures and docket photos are written to DJANGO_MEDIA_ROOT. Two things go
# wrong in production and both used to surface as a 500 on save:
#   * the path does not exist (no volume mounted), or
#   * a mounted volume is owned by root while the app runs as appuser.
# Fix what we can as root; if the configured path still is not writable, fall
# back to a path that is, loudly, so the app keeps working while the
# misconfiguration is visible in the logs and on /api/health/.
prepare_media_root() {
  local target="${DJANGO_MEDIA_ROOT:-}"
  [ -n "$target" ] || return 0

  if mkdir -p "$target" 2>/dev/null; then
    if running_as_root && have_app_user; then
      # The mount point itself needs fixing too, not just the media directory:
      # Railway attaches volumes as root-owned and mode 700, so appuser cannot
      # even traverse into it, however the child is owned.
      local parent
      parent="$(dirname "$target")"
      chown "$APP_USER:$APP_USER" "$parent" 2>/dev/null || true
      chmod 755 "$parent" 2>/dev/null || true
      chown -R "$APP_USER:$APP_USER" "$target" 2>/dev/null || true
    fi
    if writable_by_app_user "$target"; then
      echo "Media root ready at ${target}."
      return 0
    fi
  fi

  echo "" >&2
  echo "WARNING: media root '${target}' is not writable." >&2
  echo "  Uploaded signatures and docket photos will be stored at" >&2
  echo "  ${FALLBACK_MEDIA_ROOT} instead, and LOST on the next deploy." >&2
  echo "  On Railway: add a Volume to this service mounted at the parent of" >&2
  echo "  '${target}' (for DJANGO_MEDIA_ROOT=/data/media, mount /data)." >&2
  echo "" >&2

  export DJANGO_MEDIA_ROOT="$FALLBACK_MEDIA_ROOT"
  mkdir -p "$FALLBACK_MEDIA_ROOT"
  if running_as_root && have_app_user; then
    chown -R "$APP_USER:$APP_USER" "$FALLBACK_MEDIA_ROOT" 2>/dev/null || true
  fi
}

if [ -n "${POSTGRES_HOST:-}" ] || [ -n "${DATABASE_URL:-}" ]; then
  wait_for_postgres
  echo "Postgres is up."
fi

prepare_media_root

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

# Drop privileges for the long-running process. Everything above needed root to
# fix up a volume mount; nothing below does.
if running_as_root && have_app_user; then
  exec setpriv --reuid="$APP_USER" --regid="$APP_USER" --init-groups "$@"
fi

exec "$@"
