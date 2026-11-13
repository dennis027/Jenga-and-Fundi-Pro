#!/bin/sh
set -e

# Apply database migrations on start-up (set RUN_MIGRATIONS=0 to skip, e.g.
# when running several replicas and migrating from a one-off job instead).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput
fi

exec "$@"
