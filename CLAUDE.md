# CLAUDE.md

## What this is

`transparent-fastapi`: a Prometheus instrumentation library for FastAPI. One call — `install(app)` — wires up HTTP request metrics, event-loop lag, threadpool saturation, and BackgroundTasks instrumentation, with disciplined cardinality.

The library proper is `src/transparent_fastapi/`. Everything else exists to verify, demo, or deploy it — not to ship.

## Layout

| Path | Role |
|---|---|
| `src/transparent_fastapi/` | THE LIBRARY — published to PyPI as `transparent-fastapi` |
| `src/test_server/` | workspace member; demo app baked into the docker image. **NOT shipped** |
| `deploy/source/` | docker-compose stack that builds the demo app from the workspace source tree (app + Prometheus + Grafana + helper scripts). The default dev stack. |
| `deploy/live/` | sibling stack that installs `transparent-fastapi` from PyPI instead of the source tree. Used to verify a published wheel end-to-end against the same observability harness. |

Both stacks define an on-demand `grafana-mcp` service under the `tools` profile, exposed by `.mcp.json` as `grafana-source` and `grafana-live` respectively — Claude Code uses these for stdio access to whichever stack is up.
| `tests/` | smoke tests guarding the public `install()` contract |

uv workspace — `uv sync` from root installs both packages editable into one `.venv/`.

## Don't break these

- **Cardinality.** Route labels are FastAPI path templates (`/users/{id}`), never raw URLs. Unmatched paths collapse to `<unmatched>`. Methods are allowlisted; anything else is `OTHER`. The library's whole value proposition is being safe to run in production — guard the relevant tests in `tests/test_smoke.py`.
- **`install(app)` signature.** Adding optional kwargs is fine. Removing or renaming existing ones (`excluded_paths`, `background_task_metrics`) is a breaking change — bump the major version.
- **Monkey-patch idempotency.** `install_patch()` mutates `starlette.background.BackgroundTasks.add_task` process-globally; multiple calls must not double-wrap. The `_observability_wrapped` sentinel attribute guards this.

## Quick reference

```bash
uv sync                                                           # set up venv
.venv/bin/pytest                                                  # 6 smoke tests
docker compose -f deploy/source/docker-compose.yml up -d --build  # dev stack (source build)
deploy/source/scripts/deploy.sh status                            # health-check
deploy/source/scripts/deploy.sh load-medium                       # locust load (load-high for heavier)
docker compose -f deploy/live/docker-compose.yml up -d --build    # release verification stack
uv build                                                          # wheel + sdist
```

## Already considered, rejected

Don't reintroduce these — each was tried and removed for stated reasons:

- **`examples/` folder.** Demo code lives in `src/test_server/app.py`. The README handles documentation snippets.
- **`docker/` folder.** Dockerfiles live next to what they build — currently only `src/test_server/Dockerfile`, a multi-stage file with two targets (`source-build` and `live-build`) selected by the consuming compose file (`deploy/source/` and `deploy/live/` respectively).
- **Root-level wrapper scripts** (`local.sh`, `dev.sh`, etc.). `docker compose -f deploy/source/docker-compose.yml ...` works from the project root unchanged because compose paths anchor to the compose file's directory, not cwd. A wrapper hides this fact rather than solving anything. See `deploy/source/CLAUDE.md` for the path semantics.

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

### Two PR shapes

Releases are driven entirely by which PR shape merges. Most PRs are the first kind; release PRs are occasional.

| | Feature/fix PR (common) | Release PR (occasional) |
|---|---|---|
| Bumps `pyproject.toml` version? | no | yes |
| Touches `CHANGELOG.md`? | adds a line under `## [Unreleased]` | flips `[Unreleased]` → `[X.Y.Z]` and adds a fresh empty `[Unreleased]` |
| What happens on merge? | nothing publishes — `release.yml` sees no version-field change and no-ops | `release.yml` runs, pauses on the `pypi` environment for your approval, then publishes |

A release PR can be the same PR as a feature when shipping a one-feature release — that's a choice, not the default. The default is: ship features under `[Unreleased]` until enough has accumulated, then open a small dedicated release PR.

### Per-PR changelog discipline (feature/fix PRs)

Every PR that changes user-visible behavior adds a line under `## [Unreleased]` in `CHANGELOG.md`, in the right section (`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`). Pure CI/refactor/docs PRs don't need an entry.

### Cutting a release (release PRs)

The release is fully driven by a version-field bump on `master`. No manual tagging.

**Step 1 — open the release PR.** Two edits, nothing else:

1. `CHANGELOG.md`:
   - rename `## [Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD`
   - add a fresh empty `## [Unreleased]` above it
   - update the link refs at the bottom: bump `[Unreleased]: .../compare/vX.Y.Z...HEAD` and add `[X.Y.Z]: .../releases/tag/vX.Y.Z`
2. `pyproject.toml`: bump `version = "X.Y.Z"`.

**Step 2 — merge the PR.** `ci.yml` runs on the PR as usual. After merge, `release.yml` triggers on `push: master`, detects the version-field change vs the previous commit, builds + smoke-tests the wheel, and refuses to proceed if `vX.Y.Z` already exists as a tag.

**Step 3 — approve the publish.** The workflow then **pauses on the `pypi` environment** waiting for required-reviewer approval. Go to the **Actions tab → the running "Release" workflow → "Review deployments" → check `pypi` → "Approve and deploy"**. This click is the safety belt against an accidental version-field bump becoming an immutable PyPI publish — don't disable it.

**Step 4 — workflow finishes the rest automatically.** After approval it publishes via OIDC, tags the release commit `vX.Y.Z`, and creates a GitHub Release with the changelog section as body and the wheel + sdist attached.

**Step 5 (optional) — verify the published wheel end-to-end.** Bump the default `TFA_VERSION` in `src/test_server/Dockerfile` (the `live-build` stage) and `deploy/live/docker-compose.yml` to the new version (the release-PR diff that flips `[Unreleased]` should also touch these), then `TFA_VERSION=X.Y.Z deploy/live/scripts/deploy.sh up`. Same dashboards as the regular dev stack, but the `app` container installs from PyPI. See `deploy/live/CLAUDE.md` for details.

### One-time setup before the first release works

- **PyPI** → project → Publishing → add a GitHub publisher: `owner = Ashish-Github193`, `repository = transparent-fastapi`, `workflow = release.yml`, `environment = pypi`.
- **GitHub** → repo Settings → Environments → create `pypi` and add yourself as a **required reviewer**. This is the manual gate that approves each publish.
