#!/bin/sh
set -e

echo "Aplicando migrações do banco..."
alembic upgrade head

if [ "${POPULAR_DEMO:-false}" = "true" ]; then
  python -m scripts.popular_banco || true
fi

exec "$@"
