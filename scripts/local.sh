#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.12 .venv
fi
uv pip sync --python .venv/bin/python backend/requirements.lock
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm ci && npm run build)
elif [ ! -f frontend/dist/index.html ]; then
  echo 'Build frontend first with npm ci && npm run build in frontend/.' >&2
  exit 1
fi
exec .venv/bin/python scripts/local_runtime.py
