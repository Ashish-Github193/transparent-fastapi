# Configuration values for the local stack.
# All overridable via environment variables.

# Host-side ports
export APP_PORT="${APP_PORT:-8000}"
export PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
export GRAFANA_PORT="${GRAFANA_PORT:-3000}"

# Default load profile for `deploy.sh load-async`
export LOCUST_USERS="${LOCUST_USERS:-20}"
export LOCUST_SPAWN_RATE="${LOCUST_SPAWN_RATE:-5}"

# Sync demo intentionally low-concurrency — sync handler blocks the loop, so
# high concurrency just queues forever instead of producing useful signal.
export LOCUST_SYNC_USERS="${LOCUST_SYNC_USERS:-4}"
export LOCUST_SYNC_SPAWN_RATE="${LOCUST_SYNC_SPAWN_RATE:-1}"
