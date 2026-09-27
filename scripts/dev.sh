#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
BACKEND_ENV="$ROOT_DIR/backend/.env"
WEB_ENV="$WEB_DIR/.env"
ROOT_ENV="$ROOT_DIR/.env"

BACKEND_PID=""
WEB_PID=""

load_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

value_for_key() {
  local file="$1"
  local key="$2"
  [[ -f "$file" ]] || return 1
  local line
  line="$(grep -E "^[[:space:]]*${key}=" "$file" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 1
  local value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  [[ -n "$value" ]]
}

require_file() {
  local file="$1"
  local example="$2"
  if [[ ! -f "$file" ]]; then
    printf 'Missing %s. Copy %s and fill it.\n' "$file" "$example" >&2
    exit 1
  fi
}

require_keys() {
  local file="$1"
  shift
  local missing=()
  for key in "$@"; do
    if ! value_for_key "$file" "$key"; then
      missing+=("$key")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    printf 'Missing required env values in %s:\n' "$file" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    exit 1
  fi
}

require_any_key() {
  local file="$1"
  shift
  for key in "$@"; do
    if value_for_key "$file" "$key"; then
      return
    fi
  done
  printf 'Missing required env value in %s. Set one of:\n' "$file" >&2
  printf '  - %s\n' "$@" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  fi
}

start_neo4j() {
  require_command docker
  if docker ps --format '{{.Names}}' | grep -qx 'rag-neo4j'; then
    printf 'Neo4j already running: rag-neo4j\n'
    return
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx 'rag-neo4j'; then
    printf 'Starting existing Neo4j container: rag-neo4j\n'
    docker start rag-neo4j >/dev/null
    return
  fi
  printf 'Creating Neo4j container: rag-neo4j\n'
  docker run -d --name rag-neo4j \
    -p 7474:7474 \
    -p 7687:7687 \
    -e "NEO4J_AUTH=${NEO4J_USERNAME:-neo4j}/${NEO4J_PASSWORD:-password123}" \
    neo4j:5 >/dev/null
}

cleanup() {
  if [[ -n "$WEB_PID" ]] && kill -0 "$WEB_PID" >/dev/null 2>&1; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

main() {
  require_command uv
  require_command bun

  unset BACKEND_DATABASE_PATH TURSO_DATABASE_URL TURSO_CONNECTION_URL TURSO_AUTH_TOKEN

  require_file "$BACKEND_ENV" "$ROOT_DIR/backend/.env.example"
  require_file "$WEB_ENV" "$WEB_DIR/.env.example"

  load_env_file "$ROOT_ENV"
  load_env_file "$BACKEND_ENV"
  load_env_file "$WEB_ENV"

  require_keys "$BACKEND_ENV" \
    BACKEND_INTERNAL_SECRET \
    CREDENTIAL_ENCRYPTION_KEY \
    TURSO_AUTH_TOKEN \
    NEO4J_URI \
    NEO4J_USERNAME \
    NEO4J_PASSWORD

  require_any_key "$BACKEND_ENV" TURSO_DATABASE_URL TURSO_CONNECTION_URL

  require_keys "$WEB_ENV" \
    TURSO_CONNECTION_URL \
    TURSO_AUTH_TOKEN \
    BETTER_AUTH_SECRET \
    BETTER_AUTH_URL \
    BACKEND_URL \
    BACKEND_INTERNAL_SECRET

  if [[ "${BACKEND_INTERNAL_SECRET:-}" == "change-me" ]]; then
    printf 'BACKEND_INTERNAL_SECRET must not be change-me.\n' >&2
    exit 1
  fi

  printf 'Backend Turso URL: %s\n' "${TURSO_DATABASE_URL:-${TURSO_CONNECTION_URL:-}}"

  start_neo4j

  trap cleanup EXIT INT TERM

  printf 'Starting Flask backend on http://localhost:5000\n'
  (cd "$ROOT_DIR" && uv run flask --app backend.run run --host 0.0.0.0 --port 5000) &
  BACKEND_PID="$!"

  printf 'Starting Next.js web on http://localhost:3000\n'
  (cd "$WEB_DIR" && bun run dev) &
  WEB_PID="$!"

  wait -n "$BACKEND_PID" "$WEB_PID"
}

main "$@"
