#!/bin/sh
set -e

# Started as root: make the media mount writable, then re-run as "app".
if [ "$(id -u)" = "0" ]; then
  MEDIA_DIR="${MEDIA_ROOT:-/data/media}"
  mkdir -p "$MEDIA_DIR"
  chown app:app "$MEDIA_DIR" 2>/dev/null || true
  # HOME must follow the user: libpq looks for ~/.postgresql/ client certs on SSL
  # connections (Neon) and fails if HOME still points at the unreadable /root.
  export HOME=/home/app USER=app
  exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

# Apply database migrations on start-up (set RUN_MIGRATIONS=0 to skip, e.g.
# when running several replicas and migrating from a one-off job instead).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput
  if [ "${USE_DB_CACHE:-False}" = "True" ] && [ -z "${REDIS_URL:-}" ]; then
    python manage.py createcachetable
  fi
fi

exec "$@"
