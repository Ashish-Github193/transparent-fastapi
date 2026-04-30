# transparent-fastapi

Drop-in Prometheus metrics for FastAPI. One line of setup, no per-route changes, disciplined cardinality.

## Install

```bash
pip install transparent-fastapi
```

## Use

```python
from fastapi import FastAPI
from transparent_fastapi import install

app = FastAPI()
install(app)
```

That's it. A `/metrics` endpoint is now exposed in Prometheus exposition format.

## Configuration

Two optional kwargs:

```python
install(
    app,
    excluded_paths=["/health", "/readiness"],   # noisy probes don't pollute metrics
    background_task_metrics=True,                # default; opt-out of the BackgroundTasks patch
)
```

## What it exports

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `method`, `route`, `status` |
| `http_request_duration_seconds` | Histogram | `method`, `route` |
| `http_requests_in_flight` | Gauge | — |
| `event_loop_lag_seconds` | Gauge | — |
| `threadpool_tokens` | Gauge | `state` ∈ {`total`, `borrowed`, `available`} |
| `threadpool_tasks_waiting` | Gauge | — |
| `background_task_scheduled_total` | Counter | `mode` ∈ {`async`, `threadpool`} |
| `background_task_total` | Counter | `mode` ∈ {`async`, `threadpool`}, `outcome` ∈ {`ok`, `error`} |
| `background_task_duration_seconds` | Histogram | `mode` |

### Plus, free from `prometheus_client`'s default registry

`prometheus_client` auto-registers a process collector and a Python collector. Because `transparent-fastapi`'s `/metrics` endpoint calls `generate_latest()` on the default registry, these are exposed too — you don't need to do anything:

| Metric | Type | Labels | What it tells you |
|---|---|---|---|
| `process_cpu_seconds_total` | Counter | — | CPU time consumed; `rate()` → cores in use |
| `process_resident_memory_bytes` | Gauge | — | RSS (physical memory) |
| `process_virtual_memory_bytes` | Gauge | — | VSZ |
| `process_open_fds` | Gauge | — | FDs in use; creep toward `process_max_fds` = leak |
| `process_max_fds` | Gauge | — | Soft FD limit |
| `process_start_time_seconds` | Gauge | — | Unix epoch of process start; `time() - this` = uptime |
| `python_gc_collections_total` | Counter | `generation` ∈ {`0`, `1`, `2`} | GC collections; sustained gen-2 = long-lived churn |
| `python_gc_objects_collected_total` | Counter | `generation` | Objects reclaimed per generation |
| `python_gc_objects_uncollectable_total` | Counter | `generation` | Objects GC could not free (cycles with `__del__`) |
| `python_info` | Info | `version`, `implementation`, `major`, `minor`, `patchlevel` | Python build details |

## Useful queries

```promql
# Validation-failure rate by route — Pydantic 422s already live in the status label
sum by (route) (rate(http_requests_total{status="422"}[5m]))

# 5xx error ratio
sum(rate(http_requests_total{status=~"5.."}[5m])) /
  sum(rate(http_requests_total[5m]))

# p95 latency by route
histogram_quantile(0.95,
  sum by (route, le) (rate(http_request_duration_seconds_bucket[5m])))

# Threadpool saturation — non-zero means sync work is queuing
sum(threadpool_tasks_waiting)

# Background task backlog growth (positive = scheduling outpaces completion)
sum(rate(background_task_scheduled_total[1m]))
  - sum(rate(background_task_total[1m]))

# Process uptime in seconds
time() - process_start_time_seconds
```

## Cardinality discipline

- **Routes** are FastAPI's path templates (`/users/{id}`), never raw URLs. Three different `/users/123`, `/users/124`, `/users/125` requests collapse into one time series.
- **Unmatched paths** (port scans, vulnerability probes) collapse to `route="<unmatched>"` rather than leaking the raw path as a label.
- **Methods** are allowlisted (GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS); anything else becomes `OTHER`.
- **Status** is the full numeric code (`"200"`, `"404"`); fine-grained enough for "alert when 401 spikes vs 500 spikes" without exploding cardinality.

## Limitations

`FastAPI(root_path=...)` and `app.include_router(router, prefix=...)` are handled correctly — both produce clean, prefixed templates in the `route` label. A couple of `app.mount(...)` cases are worth knowing about:

- **`StaticFiles` (and any Starlette `Mount`) records as `route="<unmatched>"`.** Starlette's `Mount` doesn't populate `request.scope["route"]` the way FastAPI's `APIRoute` does, so static-file requests share a single series with unmatched paths (port scans, typos). This is a feature for cardinality — a 100k-asset directory can't explode the time series — but it does mean static traffic isn't separately observable here. Per-asset metrics belong at the CDN / edge proxy.
- **Mounted FastAPI sub-applications share series with top-level routes.** `app.mount("/api", sub_app)` records traffic as `route="/users/{user_id}"`, *without* the `/api` prefix. This is fine when you have one mount; two mounts of the same sub-app at different paths would collide on the same series. Prefer `app.include_router(router, prefix="/api")` for FastAPI-internal composition — its templates are baked with the prefix and stay distinct.

## Local demo stack

`deploy/local/` ships a docker-compose stack (app + Prometheus + Grafana). All paths in the compose file are relative to it, so compose can be invoked directly from the project root:

```bash
docker compose -f deploy/local/docker-compose.yml up -d --build
docker compose -f deploy/local/docker-compose.yml logs -f
docker compose -f deploy/local/docker-compose.yml down            # add -v to wipe volumes
```

For health checks and locust load profiles there's a small wrapper script under `deploy/local/scripts/`:

```bash
deploy/local/scripts/deploy.sh status        # curl all three services
deploy/local/scripts/deploy.sh load-medium   # realistic medium-load profile via locust
deploy/local/scripts/deploy.sh load-high     # realistic high-load profile (same ratios)
```

`deploy.sh up`, `down`, and `logs` are also there as thin shortcuts over the compose commands above — pick whichever you prefer.

After `up`:

- app: <http://localhost:8000>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (admin/admin or anonymous Viewer)

Grafana comes pre-wired with Prometheus as the default datasource — open Explore and try `sum by (route) (rate(http_requests_total[1m]))` or `event_loop_lag_seconds` to see live numbers from whichever load profile you're driving.

## How it works (briefly)

- **HTTP metrics** are recorded by two ASGI middlewares wired up by `install(app)`. Route templates are read from `request.scope["route"].path` after dispatch, so labels are always the matched template — never a raw URL.
- **Event-loop lag** is sampled by a background task `install(app)` adds to your lifespan. It schedules a 1-second sleep and reports the delta between expected and actual wake-up.
- **Threadpool gauges** are refreshed at scrape time from anyio's default `CapacityLimiter`, so the values are always live, not polled.
- **Background task metrics** come from a one-time monkey-patch of `starlette.background.BackgroundTasks.add_task`. Your route code keeps using `background_tasks.add_task(...)` as normal; the patch wraps the func to record `ok/error` and duration, and labels by mode using starlette's own async-vs-threadpool detection.

## License

MIT
