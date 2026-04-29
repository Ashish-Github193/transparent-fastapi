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
| `background_task_total` | Counter | `mode` ∈ {`async`, `threadpool`}, `outcome` ∈ {`ok`, `error`} |
| `background_task_duration_seconds` | Histogram | `mode` |

## Cardinality discipline

- **Routes** are FastAPI's path templates (`/users/{id}`), never raw URLs. Three different `/users/123`, `/users/124`, `/users/125` requests collapse into one time series.
- **Unmatched paths** (port scans, vulnerability probes) collapse to `route="<unmatched>"` rather than leaking the raw path as a label.
- **Methods** are allowlisted (GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS); anything else becomes `OTHER`.
- **Status** is the full numeric code (`"200"`, `"404"`); fine-grained enough for "alert when 401 spikes vs 500 spikes" without exploding cardinality.

## Local demo stack

`deploy/local/` ships a docker-compose stack (app + Prometheus + Grafana). All paths in the compose file are relative to it, so compose can be invoked directly from the project root:

```bash
docker compose -f deploy/local/docker-compose.yml up -d --build
docker compose -f deploy/local/docker-compose.yml logs -f
docker compose -f deploy/local/docker-compose.yml down            # add -v to wipe volumes
```

For health checks and locust load profiles there's a small wrapper script under `deploy/local/scripts/`:

```bash
deploy/local/scripts/deploy.sh status       # curl all three services
deploy/local/scripts/deploy.sh load-async   # AsyncSleepUser (non-blocking demo)
deploy/local/scripts/deploy.sh load-sync    # SyncSleepUser (event-loop-blocking demo)
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
