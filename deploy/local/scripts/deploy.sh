#!/usr/bin/env bash
# Single entry point for the local demo stack.
#
#   ./deploy.sh up                start app + prometheus + grafana
#   ./deploy.sh down [--volumes]
#   ./deploy.sh logs [service]
#   ./deploy.sh status
#   ./deploy.sh load-medium       drive realistic medium-load traffic via locust
#   ./deploy.sh load-high         drive realistic high-load traffic via locust
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
. "$SCRIPT_DIR/config.sh"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  up                start app + prometheus + grafana (rebuilds app image)
  down [--volumes]  stop the stack; pass --volumes to also wipe data
  logs [service]    tail logs (optionally for a single service)
  status            show whether app/prometheus/grafana are reachable
  load-medium       drive realistic medium-load traffic via locust
  load-high         drive realistic high-load traffic via locust

Overridable env vars:
  APP_PORT, PROMETHEUS_PORT, GRAFANA_PORT
  LOCUST_MEDIUM_USERS, LOCUST_MEDIUM_SPAWN_RATE
  LOCUST_HIGH_USERS,   LOCUST_HIGH_SPAWN_RATE
EOF
}

cmd_up() {
  require_cmd docker
  resolve_compose
  log "starting docker compose stack..."
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build
  log "waiting for app at $APP_URL/metrics ..."
  wait_for_url "$APP_URL/metrics" 60
  log "stack is up:"
  log "  app:        $APP_URL"
  log "  prometheus: $PROMETHEUS_URL"
  log "  grafana:    $GRAFANA_URL  (admin/admin or anonymous Viewer)"
  log ""
  log "drive load with:  $(basename "$0") load-medium  (or load-high)"
}

cmd_down() {
  require_cmd docker
  resolve_compose
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" down "$@"
}

cmd_logs() {
  require_cmd docker
  resolve_compose
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs -f "$@"
}

cmd_status() {
  local fail=0 name url
  for entry in \
    "app|$APP_URL/metrics" \
    "prometheus|$PROMETHEUS_URL/-/ready" \
    "grafana|$GRAFANA_URL/api/health"
  do
    name=${entry%%|*}
    url=${entry#*|}
    if curl -sf -o /dev/null "$url"; then
      log "✓ $name reachable at $url"
    else
      warn "✗ $name not responding at $url"
      fail=$((fail + 1))
    fi
  done
  [ "$fail" -eq 0 ] || return 1
}

cmd_load_medium() {
  resolve_locust
  log "running MediumLoadUser against $APP_URL ($LOCUST_MEDIUM_USERS users, ${LOCUST_MEDIUM_SPAWN_RATE}/s spawn)"
  log "(0.5–3s think time; populates every panel without driving collapse)"
  "$LOCUST" -f "$LOCUSTFILE" --host="$APP_URL" \
    --headless -u "$LOCUST_MEDIUM_USERS" -r "$LOCUST_MEDIUM_SPAWN_RATE" \
    MediumLoadUser
}

cmd_load_high() {
  resolve_locust
  log "running HighLoadUser against $APP_URL ($LOCUST_HIGH_USERS users, ${LOCUST_HIGH_SPAWN_RATE}/s spawn)"
  log "(same ratios as medium but 0.05–0.3s think time — drives visible threadpool & latency tail pressure)"
  "$LOCUST" -f "$LOCUSTFILE" --host="$APP_URL" \
    --headless -u "$LOCUST_HIGH_USERS" -r "$LOCUST_HIGH_SPAWN_RATE" \
    HighLoadUser
}

case "${1:-}" in
  up)              cmd_up ;;
  down)            shift; cmd_down "$@" ;;
  logs)            shift; cmd_logs "$@" ;;
  status)          cmd_status ;;
  load-medium)     cmd_load_medium ;;
  load-high)       cmd_load_high ;;
  -h|--help|help|"") usage ;;
  *) err "unknown command: $1"; usage; exit 1 ;;
esac
