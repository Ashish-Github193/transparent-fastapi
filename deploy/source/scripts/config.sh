# Configuration values for the local stack.
# All overridable via environment variables.

# Host-side ports
export APP_PORT="${APP_PORT:-8000}"
export PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
export GRAFANA_PORT="${GRAFANA_PORT:-3000}"

# Medium load — steady-state, ~25 rps with 0.5–3s think time.
export LOCUST_MEDIUM_USERS="${LOCUST_MEDIUM_USERS:-50}"
export LOCUST_MEDIUM_SPAWN_RATE="${LOCUST_MEDIUM_SPAWN_RATE:-5}"

# High load — same task ratios, 0.05–0.3s think time, ~570 rps with 100 users.
export LOCUST_HIGH_USERS="${LOCUST_HIGH_USERS:-100}"
export LOCUST_HIGH_SPAWN_RATE="${LOCUST_HIGH_SPAWN_RATE:-10}"
