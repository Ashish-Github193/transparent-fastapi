# CLAUDE.md

## What this is

`transparent-fastapi`: a Prometheus instrumentation library for FastAPI. One call — `install(app)` — wires up HTTP request metrics, event-loop lag, threadpool saturation, and BackgroundTasks instrumentation, with disciplined cardinality.

The library proper is `src/transparent_fastapi/`. Everything else exists to verify, demo, or deploy it — not to ship.

## Layout

| Path | Role |
|---|---|
| `src/transparent_fastapi/` | THE LIBRARY — published to PyPI as `transparent-fastapi` |
| `src/test_server/` | workspace member; demo app baked into the docker image. **NOT shipped** |
| `deploy/local/` | docker-compose stack (app + Prometheus + Grafana) + helper scripts. Also defines an on-demand `grafana-mcp` service under the `tools` profile, used by `.mcp.json` to give Claude Code Grafana access |
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
deploy/local/scripts/deploy.sh load-medium                       # locust load (load-high for heavier)
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

## Releasing

The project follows [SemVer 2.0](https://semver.org/spec/v2.0.0.html) and [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). While we are pre-1.0, treat `0.MINOR.0` as breaking-or-feature and `0.x.PATCH` as safe fixes — i.e. bump `MINOR` whenever strict semver would say MAJOR. Cut `1.0.0` when the metric names and `install()` signature are committed-to-stable.

### What triggers which bump

Anchored to "Don't break these" above:

- **MAJOR** (post-1.0) / **MINOR** (pre-1.0) — anything a user or their dashboards/alerts would notice break:
  - removing or renaming an `install()` kwarg
  - renaming a metric family or any label key (`route`, `method`, `status`, `mode`, `outcome`, `state`)
  - changing a sentinel value (`<unmatched>`, `OTHER`)
  - removing or renaming a public symbol exported from `transparent_fastapi`
  - raising the Python or FastAPI floor in `pyproject.toml`
- **MINOR** — additive only:
  - new optional kwarg on `install()` (existing callers keep working)
  - new metric family
  - new label *value* on an existing dimension (PromQL aggregations stay correct)
- **PATCH** — invisible to users:
  - bug fixes that don't change metric output
  - perf, refactor, doc, CI, test changes

### Per-PR changelog discipline

Every PR that changes user-visible behavior adds a line under `## [Unreleased]` in `CHANGELOG.md`, in the right section (`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`). Pure CI/refactor/docs PRs don't need an entry.

### Cutting a release

The release is fully driven by a version bump on `master`. No manual tagging.

Open a PR that does exactly two things:

1. Edit `CHANGELOG.md`:
   - rename `## [Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD`
   - add a fresh empty `## [Unreleased]` above it
   - update the link refs at the bottom: bump `[Unreleased]: .../compare/vX.Y.Z...HEAD` and add `[X.Y.Z]: .../releases/tag/vX.Y.Z`
2. Bump `version = "X.Y.Z"` in `pyproject.toml`.

Merge the PR. `.github/workflows/release.yml` triggers on `push` to `master`, detects the version-field change vs the previous commit, builds, refuses to proceed if `vX.Y.Z` already exists as a tag, then waits for **manual approval on the `pypi` environment** before publishing. After publish it tags the release commit `vX.Y.Z` and creates a GitHub Release with the changelog section as body.

The environment-reviewer gate is the safety against an accidental version-field bump becoming a real PyPI publish — PyPI publishes are immutable, so don't disable it.

### One-time setup before the first release works

- **PyPI** → project → Publishing → add a GitHub publisher: `owner = Ashish-Github193`, `repository = transparent-fastapi`, `workflow = release.yml`, `environment = pypi`.
- **GitHub** → repo Settings → Environments → create `pypi` and add yourself as a **required reviewer**. This is the manual gate that approves each publish.
