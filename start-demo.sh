#!/usr/bin/env bash
# Runs the platform with fictional demo data: no Supabase or SendGrid account
# needed, nothing is saved, e-mails land in the Postausgang page.
# Login: demo / Demo-2026!
#
#   ./start-demo.sh          production build: fast, for trying and presenting
#   ./start-demo.sh --dev    Next.js dev server: hot reload for coding, but every
#                            page is compiled on first visit (can take many seconds)
#
# Ports: BACKEND_PORT (default 8000) and FRONTEND_PORT (default 3000).
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
API_URL="http://localhost:${BACKEND_PORT}"
APP_URL="http://localhost:${FRONTEND_PORT}"

if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi

(cd backend && DEMO_MODE=true API_BASE_URL="$API_URL" DEMO_FRONTEND_URL="$APP_URL" \
  ADDITIONAL_CORS_ORIGINS="$APP_URL" .venv/bin/python -m uvicorn main:app --port "$BACKEND_PORT") &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null' EXIT

cd frontend
export NEXT_PUBLIC_API_URL="$API_URL" NEXT_TELEMETRY_DISABLED=1
if [ "${1:-}" = "--dev" ]; then
  npx next dev -p "$FRONTEND_PORT"
else
  echo "Building the frontend (once per start, about a minute)..."
  npm run build >/dev/null
  echo "Demo ready at $APP_URL (login: demo / Demo-2026!)"
  npx next start -p "$FRONTEND_PORT"
fi
