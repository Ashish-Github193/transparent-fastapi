# CLAUDE.md

## What this is

A docker-compose stack (FastAPI app + Prometheus + Grafana) for local demo, building the app from the **workspace source tree**. Locust runs from the host, not in compose.

Sibling stack: `deploy/live/` — same harness but installs `transparent-fastapi` from PyPI instead, used for release verification. They're independent (separate compose project, container names, configs, scripts) — only one runs at a time on default ports.

## Path semantics — read this BEFORE "fixing" anything

Compose resolves paths against two anchors, neither of which is your shell's cwd:

| Path in YAML | Anchored to | Resolves to |
|---|---|---|
| `context: ../..` | compose file's directory | repo root |
| `dockerfile: src/test_server/Dockerfile` | the build context (= repo root) | `src/test_server/Dockerfile` |
| `./configs/prometheus.yml` (volume) | compose file's directory | `deploy/source/configs/prometheus.yml` |
| `./configs/grafana/provisioning` (volume) | compose file's directory | `deploy/source/configs/grafana/provisioning` |

That means `docker compose -f deploy/source/docker-compose.yml up` from the repo root resolves all paths identically to running `docker compose up` from inside `deploy/source/`. **Don't add a wrapper script at the repo root to abstract this** — it isn't broken. (A `local.sh` wrapper was tried and removed for exactly this reason.)

## scripts/

| File | Role |
|---|---|
| `deploy.sh` | Entry point. Subcommands: `up`, `down`, `logs`, `status`, `load-medium`, `load-high`. Resolves its own dir via `BASH_SOURCE`, so it works from any cwd. |
| `config.sh` | Variables, every one in `${VAR:-default}` form so env wins (`APP_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT`, `LOCUST_USERS`, etc.). Sourced, not run. |
| `common.sh` | Helpers: `log`/`warn`/`err`, `resolve_compose`, `resolve_locust`, `wait_for_url`. Sourced, not run. |

`deploy.sh up`/`down`/`logs` are thin shortcuts over `docker compose ... up/down/logs`. Direct compose invocation works fine — pick whichever you prefer. `status` and the `load-*` commands are the reason to use the script.

## Conventions

- **Pin image versions** (`prom/prometheus:v2.55.0`, `grafana/grafana:11.3.0`). `:latest` silently breaks reproducibility — don't introduce it.
- **Locust runs on the host, not in compose.** It's a uv dev dep at `.venv/bin/locust` (resolved by `resolve_locust` in `common.sh`). Iterating on the locustfile inside a container is friction we don't want.
- **Grafana datasource and dashboards are auto-provisioned** from `configs/grafana/provisioning/`. The dashboard exposes a `datasource` template variable (`type: datasource`, filtered to Prometheus) so the JSON is portable to any Grafana with a Prometheus datasource — no hardcoded UID dependency. Inside this stack the provisioned datasource has `isDefault: true`, so the variable auto-selects it on load. Dashboards live under `configs/grafana/provisioning/dashboards/`; the provider yaml polls every 10s with `allowUiUpdates: true`, so UI edits stick until the file changes.
- **Prometheus 5s scrape interval** (`global.scrape_interval` in `configs/prometheus.yml`). Tighter than the 15s default because a demo stack rewards faster feedback. Don't propagate this to a prod profile.
- **`grafana-mcp` is on-demand, not part of the stack.** It sits under `profiles: ["tools"]` so `compose up` ignores it. The repo-root `.mcp.json` exposes it as the `grafana-source` MCP server (`docker compose -f deploy/source/docker-compose.yml run --rm -T grafana-mcp`) — Claude Code uses it for stdio access to *this* stack's Grafana via the Grafana Labs MCP server. The sibling `deploy/live/` stack has its own `grafana-mcp` service exposed as `grafana-live`. Pinned by digest because `mcp/grafana` only ships a `:latest` tag.
