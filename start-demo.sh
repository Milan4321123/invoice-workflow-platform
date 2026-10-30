#!/usr/bin/env bash
# Runs the platform with fictional demo data: no Supabase or SendGrid account
# needed, nothing is saved, e-mails land in backend/outbox/.
# Login: demo / Demo-2026!
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi

(cd backend && DEMO_MODE=true .venv/bin/python -m uvicorn main:app --port 8000) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null' EXIT

cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
