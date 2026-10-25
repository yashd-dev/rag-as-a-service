#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log() { echo "[run.sh] $*"; }

# Start the Flask backend (default port 5000) if not already running.
if ! pgrep -f "backend\.run" >/dev/null 2>&1; then
  log "Starting backend on http://localhost:5000"
  .venv/bin/python -m backend.run > /tmp/opencode/backend.log 2>&1 &
  echo $! > /tmp/opencode/backend.pid
else
  log "Backend is already running."
fi

# Start the durable ingestion worker separately from Flask.
if ! pgrep -f "backend\.scripts\.worker" >/dev/null 2>&1; then
  log "Starting ingestion worker"
  .venv/bin/python -m backend.scripts.worker > /tmp/opencode/worker.log 2>&1 &
  echo $! > /tmp/opencode/worker.pid
else
  log "Ingestion worker is already running."
fi

# Start the Next.js frontend (default port 3000) if not already running.
if ! pgrep -f "next dev" >/dev/null 2>&1; then
  log "Starting frontend on http://localhost:3000"
  (cd web && bun run dev > /tmp/opencode/web.log 2>&1 &)
  echo $! > /tmp/opencode/web.pid
else
  log "Frontend is already running."
fi

log "RAGaaS running: backend http://localhost:5000  frontend http://localhost:3000"
log "Logs: /tmp/opencode/backend.log  /tmp/opencode/web.log"
