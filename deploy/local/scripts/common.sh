# Path resolution and helper functions shared by deploy.sh.
# Sourced, not executed — no shebang on purpose.

COMMON_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$COMMON_SH_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/../.." && pwd)"

COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"
LOCUSTFILE="$DEPLOY_DIR/locustfile.py"

APP_URL="http://127.0.0.1:${APP_PORT:-8000}"
PROMETHEUS_URL="http://127.0.0.1:${PROMETHEUS_PORT:-9090}"
GRAFANA_URL="http://127.0.0.1:${GRAFANA_PORT:-3000}"

log()  { printf "\033[1;36m▸\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "missing required command: $1"; return 1; }
}

resolve_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
  else
    err "neither 'docker compose' (v2 plugin) nor 'docker-compose' (v1) is available"
    return 1
  fi
}

resolve_locust() {
  if [ -x "$REPO_ROOT/.venv/bin/locust" ]; then
    LOCUST="$REPO_ROOT/.venv/bin/locust"
  elif command -v locust >/dev/null 2>&1; then
    LOCUST="$(command -v locust)"
  else
    err "locust not found. Install with: cd '$REPO_ROOT' && uv sync"
    return 1
  fi
}

wait_for_url() {
  local url=$1 timeout=${2:-60} elapsed=0
  while ! curl -sf -o /dev/null "$url" 2>/dev/null; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$timeout" ]; then
      err "timeout after ${timeout}s waiting for $url"
      return 1
    fi
  done
}
