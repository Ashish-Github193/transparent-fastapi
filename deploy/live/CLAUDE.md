# CLAUDE.md

## What this is

A standalone docker-compose stack that builds the demo app from the **published PyPI wheel** of `transparent-fastapi` instead of the workspace source tree. Used to verify a release end-to-end before declaring it good — same Prometheus + Grafana harness as `deploy/source/`, but the `app` container installs `transparent-fastapi==X.Y.Z` from PyPI.

Locust runs from the host, not in compose, just like `deploy/source/`.

## How it differs from deploy/source/

| | `deploy/source/` | `deploy/live/` |
|---|---|---|
| Library install | `pip install .` from workspace | `pip install transparent-fastapi==X.Y.Z` |
| Dockerfile | `src/test_server/Dockerfile`, `target: source-build` | `src/test_server/Dockerfile`, `target: live-build` |
| Compose project name | `transparent-fastapi` | `transparent-fastapi-live` |
| Container names | `tfa-app`, `tfa-prometheus`, `tfa-grafana` | `tfa-live-app`, `tfa-live-prometheus`, `tfa-live-grafana` |
| Default ports | 8000 / 9090 / 3000 | 8000 / 9090 / 3000 (same — only one stack at a time on defaults) |
| `grafana-mcp` (MCP service) | yes (under `tools` profile, exposed as `grafana-source` in `.mcp.json`) | yes (same, exposed as `grafana-live` in `.mcp.json`) |

Both stacks share the **same Dockerfile** at `src/test_server/Dockerfile` — multi-stage with two named targets (`source-build` and `live-build`) plus a shared `base`. Each compose file picks its target via `build.target:`. No build conditionals, no duplicated FROM/uvicorn/EXPOSE/CMD scaffolding.

Configs and locustfile, however, are **independent copies** between the two stacks. They don't share files. If you tweak the dashboard in `deploy/source/`, sync it here manually if the change should also apply to verification (usually it should — keep them aligned).

## Usage

```bash
deploy/live/scripts/deploy.sh up                     # default version (in docker-compose.yml)
TFA_VERSION=0.1.3 deploy/live/scripts/deploy.sh up   # pin a different version
deploy/live/scripts/deploy.sh status
deploy/live/scripts/deploy.sh load-medium            # locust against this stack
deploy/live/scripts/deploy.sh down
```

Or directly via compose:

```bash
docker compose -f deploy/live/docker-compose.yml up -d --build
```

## Per-release maintenance

In each release PR, bump the default `TFA_VERSION` in two places:

- `src/test_server/Dockerfile` — `ARG TFA_VERSION=X.Y.Z` in the `live-build` stage (build-time fallback)
- `deploy/live/docker-compose.yml` — `${TFA_VERSION:-X.Y.Z}` in the `app` build args and image tag (env-substitution fallback)

Both should match. Same release-PR diff that flips `[Unreleased]` → `[X.Y.Z]` in `CHANGELOG.md`.

## Path semantics

Same as `deploy/source/` — see that CLAUDE.md for the rules. Compose paths anchor to the compose file's directory, so `docker compose -f deploy/live/docker-compose.yml ...` works identically from any cwd.
