#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f dados/estoque.db ] || python -m scripts.popular_banco
echo "Painel: http://127.0.0.1:8000"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header --no-access-log
