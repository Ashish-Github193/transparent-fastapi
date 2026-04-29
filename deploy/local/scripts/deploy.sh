#!/usr/bin/env bash
# Single entry point for the local demo stack.
#
#   ./deploy.sh up              start app + prometheus + grafana
#   ./deploy.sh down [--volumes]
#   ./deploy.sh logs [service]
#   ./deploy.sh status
#   ./deploy.sh load-async      drive load via locust (non-blocking demo)
#   ./deploy.sh load-sync       drive load via locust (event-loop-blocking demo)
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
  load-async        drive non-blocking load with AsyncSleepUser
  load-sync         drive blocking load with SyncSleepUser

Overridable env vars:
  APP_PORT, PROMETHEUS_PORT, GRAFANA_PORT
  LOCUST_USERS, LOCUST_SPAWN_RATE
  LOCUST_SYNC_USERS, LOCUST_SYNC_SPAWN_RATE
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
  log "drive load with:  $(basename "$0") load-async   (or load-sync)"
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

cmd_load_async() {
  resolve_locust
  log "running AsyncSleepUser against $APP_URL ($LOCUST_USERS users, ${LOCUST_SPAWN_RATE}/s spawn)"
  "$LOCUST" -f "$LOCUSTFILE" --host="$APP_URL" \
    --headless -u "$LOCUST_USERS" -r "$LOCUST_SPAWN_RATE" \
    AsyncSleepUser
}

cmd_load_sync() {
  resolve_locust
  log "running SyncSleepUser against $APP_URL ($LOCUST_SYNC_USERS users, ${LOCUST_SYNC_SPAWN_RATE}/s spawn)"
  log "(low concurrency on purpose — sync blocks the loop; the goal is to *show* the lag spike, not crash the app)"
  "$LOCUST" -f "$LOCUSTFILE" --host="$APP_URL" \
    --headless -u "$LOCUST_SYNC_USERS" -r "$LOCUST_SYNC_SPAWN_RATE" \
    SyncSleepUser
}

case "${1:-}" in
  up)         cmd_up ;;
  down)       shift; cmd_down "$@" ;;
  logs)       shift; cmd_logs "$@" ;;
  status)     cmd_status ;;
  load-async) cmd_load_async ;;
  load-sync)  cmd_load_sync ;;
  -h|--help|help|"") usage ;;
  *) err "unknown command: $1"; usage; exit 1 ;;
esac
