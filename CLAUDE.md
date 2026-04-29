# CLAUDE.md

## What this is

`transparent-fastapi`: a Prometheus instrumentation library for FastAPI. One call — `install(app)` — wires up HTTP request metrics, event-loop lag, threadpool saturation, and BackgroundTasks instrumentation, with disciplined cardinality.

The library proper is `src/transparent_fastapi/`. Everything else exists to verify, demo, or deploy it — not to ship.

## Layout

| Path | Role |
|---|---|
| `src/transparent_fastapi/` | THE LIBRARY — published to PyPI as `transparent-fastapi` |
| `src/test_server/` | workspace member; demo app baked into the docker image. **NOT shipped** |
| `deploy/local/` | docker-compose stack (app + Prometheus + Grafana) + helper scripts |
| `tests/` | smoke tests guarding the public `install()` contract |

uv workspace — `uv sync` from root installs both packages editable into one `.venv/`.

## Don't break these

- **Cardinality.** Route labels are FastAPI path templates (`/users/{id}`), never raw URLs. Unmatched paths collapse to `<unmatched>`. Methods are allowlisted; anything else is `OTHER`. The library's whole value proposition is being safe to run in production — guard the relevant tests in `tests/test_smoke.py`.
- **`install(app)` signature.** Adding optional kwargs is fine. Removing or renaming existing ones (`excluded_paths`, `background_task_metrics`) is a breaking change — bump the major version.
- **Monkey-patch idempotency.** `install_patch()` mutates `starlette.background.BackgroundTasks.add_task` process-globally; multiple calls must not double-wrap. The `_observability_wrapped` sentinel attribute guards this.

## Quick reference

```bash
uv sync                                                          # set up venv
.venv/bin/pytest                                                 # 6 smoke tests
docker compose -f deploy/local/docker-compose.yml up -d --build  # demo stack
deploy/local/scripts/deploy.sh status                            # health-check
deploy/local/scripts/deploy.sh load-async                        # locust load
uv build                                                         # wheel + sdist
```

## Already considered, rejected

Don't reintroduce these — each was tried and removed for stated reasons:

- **`examples/` folder.** Demo code lives in `src/test_server/app.py`. The README handles documentation snippets.
- **`docker/` folder.** Dockerfiles live next to what they build — currently only `src/test_server/Dockerfile`.
- **Root-level wrapper scripts** (`local.sh`, `dev.sh`, etc.). `docker compose -f deploy/local/docker-compose.yml ...` works from the project root unchanged because compose paths anchor to the compose file's directory, not cwd. A wrapper hides this fact rather than solving anything. See `deploy/local/CLAUDE.md` for the path semantics.

## Python versions

- Library: `requires-python = ">=3.10"`. Don't use 3.11+ syntax in `src/transparent_fastapi/`.
- test_server / dev tooling: 3.12 is fine — it's not shipped.
